from __future__ import annotations
import bentoml
from pathlib import Path
from typing import Dict
from pydantic import Field
from paddleocr import PaddleOCR, PPStructure

from src.ocr import ppocr_raw, ppocr, ppstructure_table_raw, ppstructure_table
from src.utils import check_imagemagick_installed
from src.converters import convert_to_img, crop_image
from src.models.ocr_model import OCRResponse
from src.models.segment_model import Segment, SegmentType


@bentoml.service(
    name="image",
    resources={"cpu": "2"},
    traffic={"timeout": 60}
)
class Image:
    def __init__(self) -> None:
        check_imagemagick_installed()

    @bentoml.api
    def convert_to_img(
        self,
        file: Path,
        density: int = Field(default=300, description="Image density in DPI"),
        extension: str = Field(default="png", description="Image extension")
    ) -> Dict[int, str]:
        return convert_to_img(file, density, extension)

    @bentoml.api
    def crop_image(
        self,
        file: Path,
        left: float,
        top: float,
        width: float,
        height: float,
        extension: str = Field(default="png", description="Image extension")
    ) -> Path:
        return crop_image(file, left, top, left + width, top + height, extension)


@bentoml.service(
    name="ocr",
    resources={"gpu": 1, "cpu": "4"},
    traffic={"timeout": 60}
)
class OCR:
    def __init__(self) -> None:
        self.ocr = PaddleOCR(use_angle_cls=True, lang="en",
                             ocr_order_method="tb-xy")
        self.table_engine = PPStructure(
            recovery=True, return_ocr_result_in_table=True, layout=False, structure_version="PP-StructureV2")

    @bentoml.api
    def paddle_ocr_raw(self, file: Path) -> list:
        return ppocr_raw(self.ocr, file)

    @bentoml.api
    def paddle_ocr(self, file: Path) -> OCRResponse:
        return ppocr(self.ocr, file)

    @bentoml.api
    def paddle_table_raw(self, file: Path) -> list:
        return ppstructure_table_raw(self.table_engine, file)

    @bentoml.api
    def paddle_table(self, file: Path) -> OCRResponse:
        return ppstructure_table(self.table_engine, file)


@bentoml.service(
    name="task",
    resources={"gpu": 1, "cpu": "4"},
    traffic={"timeout": 60}
)
class Task:
    image_service = bentoml.depends(Image)
    ocr_service = bentoml.depends(OCR)

    @bentoml.api
    def images_from_file(
        self,
        file: Path,
        density: int = Field(default=300, description="Image density in DPI"),
        extension: str = Field(default="png", description="Image extension")
    ) -> Dict[int, str]:
        return self.image_service.convert_to_img(file, density, extension)

    @bentoml.api
    def process(
            self,
            file: Path,
            segments: list[Segment],
            image_density: int = Field(
                default=300, description="Image density in DPI for page images"),
            page_image_extension: str = Field(
                default="png", description="Image extension for page images"),
            segment_image_extension: str = Field(
                default="jpg", description="Image extension for segment images")
    ) -> list[Segment]:
        page_images = self.image_service.convert_to_img(
            file, image_density, page_image_extension)
        for segment in segments:
            segment.image = self.image_service.crop_image(
                page_images[segment.page_number], segment.left, segment.top, segment.width, segment.height, segment_image_extension)
            if segment.segment_type == SegmentType.Table:
                segment.ocr = self.ocr_service.paddle_table(segment.image)
            else:
                segment.ocr = self.ocr_service.paddle_ocr(segment.image)
        return segments
