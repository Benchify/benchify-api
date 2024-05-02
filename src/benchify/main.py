"""
exposes the API for benchify
"""

import os
import sys
import time
from typing import Optional
import webbrowser
import json
import ast
import requests
import jwt
import typer

from auth0.authentication.token_verifier \
    import TokenVerifier, AsymmetricSignatureVerifier

from rich import print
from rich.console import Console
from rich.markdown import Markdown

app = typer.Typer()

AUTH0_DOMAIN    = 'benchify.us.auth0.com'
AUTH0_CLIENT_ID = 'VessO49JLtBhlVXvwbCDkeXZX4mHNLFs'
ALGORITHMS      = ['RS256']
id_token        = None
current_user    = None

def validate_token(id_token):
    """
    Verify the token and its precedence
    """
    jwks_url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
    issuer = f"https://{AUTH0_DOMAIN}/"
    sign_verifier = AsymmetricSignatureVerifier(jwks_url)
    token_verifier = TokenVerifier(
        signature_verifier=sign_verifier,
        issuer=issuer,
        audience=AUTH0_CLIENT_ID)
    token_verifier.verify(id_token)

class AuthTokens:
    """
    id and access tokens
    """
    id_token: str = ""
    access_token: str = ""
    def __init__(self, my_id_token, access_token):
        self.id_token = my_id_token
        self.access_token = access_token

def login() -> AuthTokens:
    """
    Runs the device authorization flow and stores the user object in memory
    """
    device_code_payload = {
        'client_id': AUTH0_CLIENT_ID,
        'scope': 'openid profile'
    }
    login_timeout = 60
    try:
        device_code_response = requests.post(
            f"https://{AUTH0_DOMAIN}/oauth/device/code", 
            data=device_code_payload, timeout=login_timeout)
    except requests.exceptions.Timeout:
        print('Error generating the device code')
        raise typer.Exit(code=1)

    if device_code_response.status_code != 200:
        print('Error generating the device code')
        raise typer.Exit(code=1)

    print('Device code successful')
    device_code_data = device_code_response.json()

    print(
        '1. On your computer or mobile device navigate to: ', 
        device_code_data['verification_uri_complete'])
    print('2. Enter the following code: ', device_code_data['user_code'])

    try:
        webbrowser.open(device_code_data['verification_uri_complete'])
    except Exception as _browser_exception:
        pass

    token_payload = {
        'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
        'device_code': device_code_data['device_code'],
        'client_id': AUTH0_CLIENT_ID
    }

    authenticated = False
    while not authenticated:
        print('Authenticating ...')
        token_response = requests.post(
            f"https://{AUTH0_DOMAIN}/oauth/token", data=token_payload,timeout=None)

        token_data = token_response.json()
        if token_response.status_code == 200:
            print('✅ Authenticated!')
            validate_token(token_data['id_token'])
            global current_user
            current_user = jwt.decode(
                token_data['id_token'],
                algorithms=ALGORITHMS,
                options={"verify_signature": False})

            authenticated = True
            # Save the current_user.

        elif token_data['error'] not in ('authorization_pending', 'slow_down'):
            print(token_data['error_description'])
            raise typer.Exit(code=1)
        else:
            time.sleep(device_code_data['interval'])
    return AuthTokens(
        my_id_token=token_data['id_token'],
        access_token=token_data['access_token']
    )

@app.command()
def authenticate():
    """
    login if not already
    """
    if current_user is None:
        login()
    print("✅ Logged in " + str(current_user))

def get_function_source(ast_tree: ast.AST, function_name: str, code: str) -> Optional[str]:
    """
    pull out just this single function's source code
    """
    for node in ast.walk(ast_tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            start_line = node.lineno
            end_line = node.end_lineno
            function_source = '\n'.join(
                code.splitlines()[start_line - 1:end_line])
            return function_source
    # if the function was not found
    return None

@app.command()
def analyze():
    """
    send the request to analyze the function specified by the command line arguments
    and show the results
    """
    if len(sys.argv) == 1:
        print("⬇️ Please specify the file to be analyzed.")
        return

    file = sys.argv[1]

    if current_user is None:
        auth_tokens = login()
        print(f"Welcome {current_user['name']}!")
    function_str = None

    try:
        print("Scanning " + file + " ...")
        with open(file, "r") as file_reading:
            function_str = file_reading.read()
            # is there more than one function in the file?
            number_of_functions = function_str.count("def ")
            if number_of_functions > 1:
                if len(sys.argv) == 2:
                    print("Since there is more than one function in the " + \
                        "file, please specify which one you want to " + \
                        "analyze, e.g., \n$ benchify sortlib.py isort")
                    return
                tree = ast.parse(function_str)
                function_name = sys.argv[2]
                function_str = get_function_source(
                    tree, function_name, function_str)
                if function_str:
                    pass
                else:
                    print(f"🔍 Function named {sys.argv[2]} not " + \
                        f"found in {file}.")
                    return
            elif number_of_functions == 1:
                """
                there is only one function but there might be other stuff in the file
                like if name == main
                so should still to a get_function_source to get just that part
                TODO
                """
            else:
                print(f"There were no functions in {file}." + \
                    " Cannot continue 😢.")
                return
    except Exception as reading_exception:
        print(f"Encountered exception trying to read {file}: {reading_exception}." + \
            " Cannot continue 😢.")
        return
    if function_str is None:
        print(f"Error attempting to read {file}." + \
            " Cannot continue 😢.")
        return

    console = Console()
    url = "https://benchify.cloud/analyze"
    params = {'test_func': function_str}
    headers = {'Authorization': f'Bearer {auth_tokens.id_token}'}
    expected_time = ("1 minute", 60)
    print(f"Analyzing.  Should take about {expected_time[0]} ...")
    try:
        # timeout 5 times longer than the expected, to account for above average times
        response = requests.get(url, params=params, headers=headers, timeout=expected_time[1]*5)
    except requests.exceptions.Timeout:
        print("Timed out")
    console.print(response.text)

if __name__ == "__main__":
    app()
