use crate::models::chunkr::task::Status;
use crate::models::chunkr::task::Task;

pub async fn cancel_task(task_id: &str, user_id: &str) -> Result<(), Box<dyn std::error::Error>> {
    let task = Task::get_by_id(&task_id, &user_id).await?;
    match Some(task.status.clone()) {
        None => return Err("Task not found".into()),
        Some(status) if status != Status::Starting => {
            return Err(format!("Task cannot be cancelled: status is {}", status).into())
        }
        _ => {}
    }
    task.cancel().await?;
    Ok(())
}
