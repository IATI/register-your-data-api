import base64
import io
import logging
from io import BytesIO

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

import register_your_data_api.audit as audit


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


def _prepare_test_data(public_key_fh: BytesIO) -> list[tuple[str, str]]:
    """Prepare test data consisting of ciphertext and plaintext log messages

    Parameters
    ----------
    public_key_fh : BytesIO
        File handle for the public key to use for encryption.

    Returns
    -------
    list[tuple[str, str]]
        List of test case tuples in the format [ciphertext log message, plaintext log message]
    """

    TEST_RECORDS = [
        (logging.INFO, "This is an audit log message that requires encrypting"),
        (logging.FATAL, "This is another audit log message that requires encrypting"),
        (logging.WARNING, "Another message with some b64 encoded data IufqSLfAe/oIZnad8zABqCB8k"),
    ]

    enc_formatter = audit.EncryptedFormatter(public_key_fh, fmt="%(levelname)s - %(message)s")
    normal_formatter = logging.Formatter(fmt="%(levelname)s - %(message)s")

    # For each test case we make the logging record, pass the record through
    # both the encrypted and normal log formatters, and store in the test data list.
    test_data = []
    for test_case in TEST_RECORDS:
        log_record = logging.LogRecord("test-logger", test_case[0], "", 0, test_case[1], None, None, None, None)

        test_data.append((enc_formatter.format(log_record), normal_formatter.format(log_record)))

    return test_data


def test_log_formatter() -> None:
    """Test encryption and decryption of log messages"""
    # Generate a private/public key pair for testing - they key is serialised
    # to a buffer so it can be read by the formatter.
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    public_key_fh = io.BytesIO()
    public_key_fh.write(
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    public_key_fh.seek(0)

    # For each test case we just need to decrypt the symmetirc key, then use that key
    # to decrypt the log message.
    for test_case in _prepare_test_data(public_key_fh):
        symmetric_key, encrypted_data = _extract_sym_key_and_data(test_case[0], private_key)
        fernet = Fernet(symmetric_key)
        assert test_case[1] == fernet.decrypt(base64.b64decode(encrypted_data)).decode("utf-8")
