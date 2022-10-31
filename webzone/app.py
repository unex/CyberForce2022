import os

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from starlette.middleware.sessions import SessionMiddleware

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import Session, relationship


SECRET_KEY = os.environ.get("SECRET_KEY", "this_should_be_configured")
assert SECRET_KEY != "this_should_be_configured"

# SQL

DATA_HISTORIAN_URI = os.environ.get("DATA_HISTORIAN_URI")

engine = create_engine(
    DATA_HISTORIAN_URI
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class SolarArrays(Base):
    __tablename__ = "solar_arrays"

    arrayID = Column(Integer, primary_key=True, index=True)
    solarStatus = Column(Integer)
    arrayVoltage = Column(Integer)
    arrayCurrent = Column(Integer)
    arrayTemp = Column(Integer)
    trackerTilt = Column(Integer)
    trackerAzimuth = Column(Integer)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# APP

app = FastAPI()
app.mount("/assets", StaticFiles(directory="assets"), name="assets")
templates = Jinja2Templates(directory="templates")

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "session": request.session, "exc": exc},
        status_code=exc.status_code,
    )


################################
#            ROUTES            #
################################


@app.get("/")
def root(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("index.html", {"request": request, "solar_arrays": db.query(SolarArrays).all()})


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(app.url_path_for("root"))


@app.get("/generation/")
def generation(request: Request):
    return templates.TemplateResponse("generation.html", {"request": request})


@app.get("/contact/")
def contact(request: Request):
    return templates.TemplateResponse("contact.html", {"request": request})


@app.get("/manufacturing/")
def manufacturing(request: Request):
    return templates.TemplateResponse("contact.html", {"request": request})


@app.get("/admin/")
def admin(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/login/")
def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})
