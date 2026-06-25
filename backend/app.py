
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from db.database import Base, engine
from db import models

from routers.upload import router as upload_router
from extract_layouts import extract_layouts


from routers.process import router as process_router
from routers.status import router as status_router
from routers.document import router as document_router
from routers.documents import router as documents_router
from routers.delete import router as delete_router

from routers.combined import router as combined_router, generate_template_preview
from routers.edit import router as edit_router
from routers.voiceover import router as voiceover_router
from routers.preview import router as preview_router
from routers.results import router as results_router
from routers.voices import router as voices_router
from routers.personas import router as personas_router
from routers import results
from routers.agent_chat import router as agent_router
from routers.studio_upload import router as studio_upload_router
# from routers.studio_pipeline import router as studio_pipeline_router
from routers.download_pptx import router as download_pptx_router
from routers.studio_upload import router as studio_router



app = FastAPI(title="PDF to Presentation Pipeline", version="2.0")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

app.mount(
    "/outputs",
    StaticFiles(directory=str(BASE_DIR / "outputs")),
    name="outputs"
)

# Serve versioned projects from projects folder
app.mount(
    "/projects",
    StaticFiles(directory=str(BASE_DIR / "projects")),
    name="projects"
)

# Serve extracted images from the original document extraction folder
app.mount(
    "/extracted_images_docx",
    StaticFiles(directory=str(BASE_DIR / "extracted_images_docx")),
    name="extracted_images_docx"
)

def _is_temporary_template_file(path: Path) -> bool:
    name = path.name
    return "~$" in name or ".~$" in name or name.startswith(".")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)

    try:
        templates_dir = BASE_DIR / "sample_ppt"
        preview_dir = templates_dir / "previews"
        preview_dir.mkdir(parents=True, exist_ok=True)

        try:
            print("Extracting layout JSONs for templates...")
            extract_layouts(str(templates_dir))
            print("✅ Layout JSONs extracted.")
        except Exception as exc:
            print(f"⚠️ Error extracting layouts: {exc}")

        for template_file in templates_dir.iterdir():
            if template_file.suffix.lower() not in (".pptx", ".potx"):
                continue
            if _is_temporary_template_file(template_file):
                continue
            preview_file = preview_dir / f"{template_file.stem}.png"
            if not preview_file.exists():
                try:
                    generate_template_preview(template_file, preview_file)
                    print(f"✅ Generated preview for {template_file.name}")
                except Exception as exc:
                    print(f"⚠️ Could not generate preview for {template_file.name}: {exc}")
    except Exception as exc:
        print(f"⚠️ Error generating template previews on startup: {exc}")

app.include_router(upload_router)
app.include_router(process_router)
app.include_router(status_router)
app.include_router(document_router)
app.include_router(documents_router)
app.include_router(delete_router)

app.include_router(combined_router)
app.include_router(edit_router)
app.include_router(voiceover_router)
app.include_router(preview_router)
app.include_router(results.router)
app.include_router(voices_router)
app.include_router(personas_router)
app.include_router(agent_router)
app.include_router(studio_upload_router)
# app.include_router(studio_pipeline_router)
app.include_router(download_pptx_router)
app.include_router(studio_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)