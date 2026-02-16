"""Audit Log Viewer for the Register Your Data API"""

import base64
import os
import sys
from typing import Generator

import click
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from dotenv import load_dotenv


class AuditLogViewerContext:

    _use_stdin = False

    _audit_log_path: str | None = None

    _audit_log_private_key_path: str

    def __init__(self, use_stdin: bool, audit_log_path: str | None, audit_log_private_key_path: str):
        self._use_stdin = use_stdin
        self._audit_log_path = audit_log_path
        self._audit_log_private_key_path = audit_log_private_key_path

    @property
    def use_stdin(self) -> bool:
        return self._use_stdin

    @property
    def audit_log_path(self) -> str | None:
        return self._audit_log_path

    @property
    def audit_log_private_key_path(self) -> str:
        return self._audit_log_private_key_path


def decrypt_audit_log(context: AuditLogViewerContext) -> Generator[str, None, None]:
    """Decrypts and return lines from the Register Your Data API audit log

    Parameters
    ----------
    context : AuditLogViewerContext
        The context for the app.
    """

    private_key_bytes = None

    with open(context.audit_log_private_key_path, "rb") as private_key_fh:
        private_key_bytes = private_key_fh.read()

    private_key = serialization.load_pem_private_key(private_key_bytes, None)
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise AssertionError("private_key not of expected type rsa.RSAPrivateKey")

    if context.use_stdin:
        fh = sys.stdin
    else:
        fh = open(context.audit_log_path, "r")  # type: ignore

    for log_line in fh:
        key, data = _extract_sym_key_and_data(log_line, private_key)
        fernet = Fernet(key)
        yield fernet.decrypt(base64.b64decode(data)).decode("utf-8")

    if not context.use_stdin:
        fh.close()


def _extract_sym_key_and_data(encrypted_log_entry: str, private_key: rsa.RSAPrivateKey) -> tuple[str, str]:
    """Extract the symmetric encryption key and encrypted data from an encrypted log entry

    Parameters
    ----------
    encrypted_log_entry : str
        Encrypted log entry to parse.
    private_key : rsa.RSAPrivateKey
        Private key to decrypt the symmetric encryption key.

    Returns
    -------
    tuple[str, str]
        Symmetric encryuption key and encrypted data
    """

    encrypted_sym_key, encrypted_data = encrypted_log_entry.split(" ")
    symmetric_key = private_key.decrypt(
        base64.b64decode(encrypted_sym_key),
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    ).decode("utf-8")
    return symmetric_key, encrypted_data


@click.command()
@click.option("--use-stdin", is_flag=True, type=click.BOOL, default=False)
def main(use_stdin: bool) -> None:
    load_dotenv()

    audit_log_path = os.getenv("AUDIT_LOG_PATH")
    audit_log_private_key_path = os.getenv("AUDIT_LOG_PRIVATE_KEY_PATH")

    if audit_log_private_key_path is None:
        raise click.ClickException("You must set the AUDIT_LOG_PRIVATE_KEY_PATH environment vairable")

    context = AuditLogViewerContext(use_stdin, audit_log_path, audit_log_private_key_path)

    for line in decrypt_audit_log(context):
        print(line, flush=True)


if __name__ == "__main__":
    main()
