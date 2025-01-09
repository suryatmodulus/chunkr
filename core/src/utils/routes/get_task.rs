use crate::configs::postgres_config::Client;
use crate::models::chunkr::output::{OutputResponse, SegmentType};
use crate::models::chunkr::task::{Configuration, Status, TaskResponse};
use crate::utils::clients::get_pg_client;
use crate::utils::storage::services::{download_to_tempfile, generate_presigned_url};
use chrono::{DateTime, Utc};
use serde_json;

pub async fn get_task(
    task_id: String,
    user_id: String,
) -> Result<TaskResponse, Box<dyn std::error::Error>> {
    let client: Client = get_pg_client().await?;
    let task = match client
        .query_one(
            "SELECT * FROM TASKS WHERE task_id = $1 AND user_id = $2",
            &[&task_id, &user_id],
        )
        .await
    {
        Ok(row) => row,
        Err(e) if e.code().map(|c| c.code()) == Some("P0002") => {
            return Err("Task not found".into());
        }
        Err(e) => return Err(e.into()),
    };

    let expires_at: Option<DateTime<Utc>> = task.get("expires_at");
    if expires_at.is_some() && expires_at.unwrap() < Utc::now() {
        return Err("Task expired".into());
    }

    create_task_from_row(&task).await
}

pub async fn create_task_from_row(
    row: &tokio_postgres::Row,
) -> Result<TaskResponse, Box<dyn std::error::Error>> {
    let task_id: String = row.get("task_id");
    let status: Status = row
        .get::<_, Option<String>>("status")
        .and_then(|m| m.parse().ok())
        .ok_or("Invalid status")?;
    let created_at: DateTime<Utc> = row.get("created_at");
    let finished_at: Option<DateTime<Utc>> = row.get("finished_at");
    let expires_at: Option<DateTime<Utc>> = row.get("expires_at");
    let message = row.get::<_, Option<String>>("message").unwrap_or_default();
    let file_name = row.get::<_, Option<String>>("file_name");
    let page_count = row.get::<_, Option<i32>>("page_count");
    let s3_pdf_location: Option<String> = row.get("pdf_location");
    let pdf_location = match s3_pdf_location {
        Some(location) => generate_presigned_url(&location, true, None).await.ok(),
        None => None,
    };
    let input_location: String = row.get("input_location");
    let input_file_url = generate_presigned_url(&input_location, true, None)
        .await
        .map_err(|_| "Error getting input file url")?;

    let output_location: String = row.get("output_location");
    let output = if status == Status::Succeeded {
        Some(process_output(&output_location).await?)
    } else {
        None
    };

    let task_url: Option<String> = row.get("task_url");
    let configuration: Configuration = row
        .get::<_, Option<String>>("configuration")
        .and_then(|c| serde_json::from_str(&c).ok())
        .ok_or("Invalid configuration")?;

    Ok(TaskResponse {
        task_id,
        status,
        created_at,
        finished_at,
        expires_at,
        message,
        output,
        input_file_url: Some(input_file_url),
        task_url,
        configuration,
        file_name,
        page_count,
        pdf_url: pdf_location.map(|s| s.to_string()),
    })
}

async fn process_output(
    output_location: &str,
) -> Result<OutputResponse, Box<dyn std::error::Error>> {
    let temp_file = download_to_tempfile(output_location, None).await?;
    let json_content: String = tokio::fs::read_to_string(temp_file.path()).await?;

    let mut output_response: OutputResponse = match serde_json::from_str(&json_content) {
        Ok(response) => response,
        Err(e) => {
            return Err(format!(
                "Invalid `output` JSON format for location {}: {}",
                output_location, e
            )
            .into());
        }
    };

    for chunk in &mut output_response.chunks {
        for segment in &mut chunk.segments {
            if let Some(image) = segment.image.as_ref() {
                let url = generate_presigned_url(image, true, None).await.ok();
                segment.image = url.clone();
                if segment.segment_type == SegmentType::Picture {
                    segment.html = Some(format!(
                        "<img src=\"{}\" />",
                        url.clone().unwrap_or_default()
                    ));
                    segment.markdown =
                        Some(format!("![Image]({})", url.clone().unwrap_or_default()));
                }
            }
        }
    }

    Ok(output_response)
}
