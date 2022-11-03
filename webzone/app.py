import os
import asyncio
from base64 import urlsafe_b64encode, urlsafe_b64decode
from io import BytesIO
from datetime import datetime
import smtplib
from typing import Optional


from fastapi import (
    FastAPI,
    Request,
    Depends,
    HTTPException,
    Form,
    File,
    UploadFile,
    status,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from starlette.middleware.sessions import SessionMiddleware
from itsdangerous.url_safe import URLSafeSerializer

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import Session, relationship

import ldap

from ftplib import FTP
from smtplib import SMTP
from imaplib import IMAP4
from email.message import EmailMessage


SECRET_KEY = os.environ.get("SECRET_KEY", "this_should_be_configured")
assert SECRET_KEY != "this_should_be_configured"

# SQL

DATA_HISTORIAN_URI = os.environ.get("DATA_HISTORIAN_URI")

# LDAP
LDAP_URI = os.environ.get("LDAP_URI")

# FTP
FTP_URI = os.environ.get("FTP_URI")

# EMAIL
MAILMAN_URI, MAILMAIN_USER, MAILMAN_PASS = os.environ.get("MAILMAN").split(",")


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


# Auth


SERIALIZER = URLSafeSerializer(SECRET_KEY)


def get_user(request: Request):
    if "user" in request.session:
        return SERIALIZER.loads(request.session["user"])


def is_admin(request: Request, user=Depends(get_user)):
    if user["admin"] != True:  # security 100
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    return user


# APP

app = FastAPI()
app.mount("/assets", StaticFiles(directory="assets"), name="assets")
templates = Jinja2Templates(directory="templates")
templates.env.filters["b64"] = lambda s: urlsafe_b64encode(s.encode()).decode()

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)


@app.on_event("startup")
def on_startup():
    engine = create_engine(DATA_HISTORIAN_URI, connect_args={"connect_timeout": 10})
    app.sql = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)


def get_db():
    db = app.sql()
    try:
        yield db
    finally:
        db.close()


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "exc": exc, "user": get_user(request)},
        status_code=exc.status_code,
    )


################################
#            ROUTES            #
################################


@app.get("/")
def root(
    request: Request, user: dict = Depends(get_user), db: Session = Depends(get_db)
):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "user": user, "solar_arrays": db.query(SolarArrays).all()},
    )


@app.get("/logout")
def logout(request: Request, user: dict = Depends(get_user)):
    request.session.clear()
    return RedirectResponse(app.url_path_for("root"))


@app.get("/generation/")
def generation(request: Request, user: dict = Depends(get_user)):
    return templates.TemplateResponse(
        "generation.html", {"request": request, "user": user}
    )


@app.get("/contact/")
def contact(request: Request, user: dict = Depends(get_user)):
    return templates.TemplateResponse(
        "contact.html", {"request": request, "user": user}
    )


@app.post("/contact/")
def submit_contact(
    request: Request,
    user: dict = Depends(get_user),
    name: str = Form(),
    email: str = Form(),
    phone: str = Form(),
    file: Optional[UploadFile] = None,
):
    message = [
        "New contact page submission",
        "---------------------------",
        "",
        f"Name: {name}",
        f"Email: {email}",
        f"Phone: {phone}",
        "",
    ]

    if file:
        filename = f"{datetime.utcnow().strftime('%b-%d-%Y_%H%M%S')}_{file.filename}"

        # upload the file file to the file fileserver
        with connect_ftp() as ftp:
            ftp.storbinary(f"STOR {filename}", file.file)

        message.append(f"Uploaded file: {filename}")

    # send an email
    mailboi = SMTP(MAILMAN_URI)
    mailboi.login(MAILMAIN_USER, MAILMAN_PASS)

    msg = EmailMessage()
    msg.set_content("\n".join(message))
    msg['subject'] = "New contact page submission"
    msg['to'] = MAILMAIN_USER
    msg['from'] = "noreply@sunpartners.local"

    mailboi.send_message(msg)
    mailboi.quit()

    return templates.TemplateResponse(
        "contact.html",
        {
            "request": request,
            "user": user,
            "message": '<div class="alert alert-success" role="alert">Success!</div>',
        },
    )


@app.get("/manufacturing/")
def manufacturing(request: Request, user: dict = Depends(get_user)):
    return templates.TemplateResponse(
        "contact.html", {"request": request, "user": user}
    )


def connect_ftp():
    u, p = (
        FTP_URI.replace("ftp://", "").split("@")[0].split(":")
    )  # WHY DO I HAVE TO DO THIS MYSELF
    addr = FTP_URI.split("@")[1]

    return FTP(addr, u, p)


@app.get("/admin/")
def admin(request: Request, user: dict = Depends(is_admin)):
    files = []

    with connect_ftp() as ftp:
        ftp.retrlines(
            "NLST", lambda file: files.append(file)  # callbacks what year is it
        )

    emails = []

    mmm = IMAP4(MAILMAN_URI)
    mmm.login(MAILMAIN_USER, MAILMAN_PASS)
    mmm.select()

    typ, data = mmm.search(None, 'ALL')

    for num in data[0].split():
        typ, data = mmm.fetch(num, '(RFC822)')
        emails.append(data[0][1].decode())

    mmm.close()
    mmm.logout()

    return templates.TemplateResponse(
        "admin.html", {"request": request, "user": user, "files": files, "emails": emails}
    )


@app.get("/admin/file/{file}")
def admin_file(request: Request, file: str, user: dict = Depends(is_admin)):
    fname = urlsafe_b64decode(
        file
    ).decode()  # not a security feature, just makes the urls less dumb

    fp = BytesIO()

    with connect_ftp() as ftp:
        ftp.retrbinary(f"RETR {fname}", fp.write)

    fp.seek(0)

    return StreamingResponse(
        fp, headers={"Content-Disposition": f'attachment; filename="{fname}"'}
    )  # can't believe this works


@app.get("/login/")
def login(request: Request, user: dict = Depends(get_user)):
    return templates.TemplateResponse("login.html", {"request": request, "user": user})


@app.post("/login/")
def do_login(request: Request):
    # dirty async hack
    data = asyncio.run(request.form())

    user = data["u"]

    conn = ldap.initialize(LDAP_URI)
    conn.protocol_version = 3
    conn.set_option(ldap.OPT_REFERRALS, 0)

    try:
        # try logging in to LDAP with provided creds
        conn.simple_bind_s(f"{user}@corp.vv.local", data["p"])

        # search users in domain, get the name and groups they are a member of
        s = conn.search(
            "cn=users,dc=corp,dc=vv,dc=local",
            ldap.SCOPE_SUBTREE,
            f"cn={user}",
            ["name", "memberOf"],
        )
        _, r = conn.result(s, 1)

        r = r[0][1]
        groups = [
            ldap.dn.str2dn(g)[0][0][1] for g in r.get("memberOf", [])
        ]  # don't question me it works

        current_user = {
            "name": r["name"][0].decode(),
            "admin": "Web Admins" in groups,  # good security
        }

        # in prod this would be shit but this is fantasy land
        request.session["user"] = SERIALIZER.dumps(current_user)

        return RedirectResponse(
            app.url_path_for("root"), status_code=status.HTTP_302_FOUND
        )

    except ldap.INVALID_CREDENTIALS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Credentials"
        )

    finally:
        conn.unbind()
