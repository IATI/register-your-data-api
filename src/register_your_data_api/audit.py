import base64
import logging
from typing import BinaryIO, Literal

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_public_key


class EncryptedFormatter(logging.Formatter):
    """Formatter for Python Logging objects that encrypts the log contents"""

    def __init__(
        self,
        public_key_fh: BinaryIO,
        fmt: str | None = None,
        datefmt: str | None = None,
        style: Literal["%", "{", "$"] = "%",
        validate: bool = True,
    ) -> None:
        """Setup the formatter

        Parameters
        ----------
        public_key_fh : BinaryIO
            File handle for the public key (in PEM format) that will be used to encrypt the symmetric key.
        fmt : str, optional
            Format string for the log entry, by default None
        datefmt : str, optional
            Format string for the log entry date formats, by default None
        style : str, optional
            Determines how forma tstring will be merged with data, by default "%"
        validate : bool, optional
            Validate format and style strings, by default True
        """
        super().__init__(fmt=fmt, datefmt=datefmt, style=style, validate=validate)

        # Load PEM public key from provided filename.
        self._public_key = load_pem_public_key(public_key_fh.read())
        if not isinstance(self._public_key, rsa.RSAPublicKey):
            raise RuntimeError("Audit log public key not RSA")

        # Generate a symmetric key for this instance and setup the symmetric cipher.
        self._symmetric_key = Fernet.generate_key()
        self._fernet = Fernet(self._symmetric_key)

        # Encrypt the symmetric key and base-64 encode for logging.
        self._enc_sym_key = self._public_key.encrypt(
            self._symmetric_key,
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
        )
        self._enc_sym_key_b64 = base64.b64encode(self._enc_sym_key).decode("utf-8")

    def _encrypt(self, plain_text: str) -> str:
        """Use symmetric encryption to encrypt a log string.

        Parameters
        ----------
        plain_text : str
            Plain text log string to encrypt.

        Returns
        -------
        str
            Ciphertext
        """
        ciphertext = self._fernet.encrypt(plain_text.encode(encoding="utf-8"))
        return base64.b64encode(ciphertext).decode(encoding="utf-8")

    def format(self, record: logging.LogRecord) -> str:
        """Format and encrypt a log string.

        Parameters
        ----------
        record : logging.LogRecord
            Log record to format and encrypt

        Returns
        -------
        str
            Encrypted log string.
        """
        log_entry = super().format(record)
        return f"{self._enc_sym_key_b64} {self._encrypt(log_entry)}"
