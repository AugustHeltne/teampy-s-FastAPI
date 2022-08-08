import json
from fastapi import FastAPI
from starlette.config import Config
from starlette.requests import Request
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import HTMLResponse, RedirectResponse
from authlib.integrations.starlette_client import OAuth, OAuthError
import requests
from requests.structures import CaseInsensitiveDict

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="insert a secret key here")

config = Config('.env')
oauth = OAuth(config)

CONF_URL = 'https://auth.dataporten.no/.well-known/openid-configuration'
oauth.register(
    name='feide',
    server_metadata_url=CONF_URL,
    client_kwargs={
        'scope': 'openid'
    }
)


def get_user_data(bearer_token):
    url = "https://api.dataporten.no/userinfo/v1/userinfo"
    headers = CaseInsensitiveDict()
    headers["Accept"] = "application/json"
    headers["Authorization"] = f"Bearer {bearer_token}"
    resp = requests.get(url, headers=headers)
    return str(resp.status_code) + " - " + str(resp.content)


@app.get('/')
async def homepage(request: Request):
    user = request.session.get('user')
    if user:
        data = json.dumps(user)
        html = ""
        html += (f"<div> Scope: {request.session.get('scope')} </div>")
        html += (f"<div> Bearer_token: {request.session.get('bearer_token')} </div>")
        html += (f"<div> Userinfo: {request.session.get('user_data')}</div>")
        html += (f"<div> OAuth Response: {data} </div>")
        html += '<a href="/logout">logout</a>'
        return HTMLResponse(html)
    return HTMLResponse('<a href="/login">login</a>')


@app.get('/login')
async def login(request: Request):
    redirect_uri = request.url_for('auth')
    return await oauth.feide.authorize_redirect(request, redirect_uri)


@app.get('/auth')
async def auth(request: Request):
    try:
        token = await oauth.feide.authorize_access_token(request)
    except OAuthError as error:
        return HTMLResponse(f'<h1>{error.error}</h1>')
    bearer_token = token.get('access_token')
    request.session["scope"] = token.get("scope")
    request.session["bearer_token"] = bearer_token
    request.session["user_data"] = get_user_data(bearer_token)
    user = token.get('userinfo')
    print(token)
    if user:
        request.session['user'] = dict(user)
    return RedirectResponse(url='/')


@app.get('/logout')
async def logout(request: Request):
    request.session.pop('user', None)
    return RedirectResponse(url='/')


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000)
