import os

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from starlette.middleware.sessions import SessionMiddleware

SECRET_KEY = os.environ.get("SECRET_KEY", "this_should_be_configured")
assert SECRET_KEY != "this_should_be_configured"

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
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
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(app.url_path_for("root"))


@app.get("/generation/")
async def root(request: Request):
    return templates.TemplateResponse("generation.html", {"request": request})


@app.get("/contact/")
async def root(request: Request):
    return templates.TemplateResponse("contact.html", {"request": request})


@app.get("/admin/")
async def root(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/login/")
async def root(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})
