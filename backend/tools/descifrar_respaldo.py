"""
Descifra un respaldo diario de CuadraMe (cuadrame_backup_AAAA-MM-DD.cmbk).

Uso:
    python descifrar_respaldo.py respaldo.cmbk salida.json            # pide la frase por teclado
    BACKUP_PASSPHRASE="..." python descifrar_respaldo.py respaldo.cmbk salida.json

Solo necesita el paquete `cryptography` (pip install cryptography). Es independiente del backend
a propósito: debe funcionar aunque el servidor ya no exista. Formato y restauración completa en
docs/RESTAURAR_RESPALDO.md.

Formato: b"CMBK1" | sal(16) | nonce(12) | AES-256-GCM(gzip(json)); clave = PBKDF2-HMAC-SHA256
(frase, sal, 600 000 iteraciones); "CMBK1" es dato autenticado.
"""
import getpass
import gzip
import os
import sys

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = b"CMBK1"
ITERACIONES = 600_000


def descifrar(blob: bytes, frase: str) -> bytes:
    """Devuelve el JSON (ya descomprimido). ValueError si la frase es incorrecta o el archivo se alteró."""
    if not blob.startswith(MAGIC) or len(blob) < len(MAGIC) + 28 + 16:
        raise ValueError("No es un respaldo de CuadraMe (formato desconocido)")
    sal = blob[len(MAGIC):len(MAGIC) + 16]
    nonce = blob[len(MAGIC) + 16:len(MAGIC) + 28]
    clave = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=sal, iterations=ITERACIONES).derive(frase.encode("utf-8"))
    try:
        return gzip.decompress(AESGCM(clave).decrypt(nonce, blob[len(MAGIC) + 28:], MAGIC))
    except Exception as e:  # noqa: BLE001
        raise ValueError("Frase incorrecta o archivo alterado") from e


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    entrada, salida = argv[1], argv[2]
    frase = os.environ.get("BACKUP_PASSPHRASE") or getpass.getpass("Frase (BACKUP_PASSPHRASE): ")
    with open(entrada, "rb") as f:
        blob = f.read()
    try:
        datos = descifrar(blob, frase)
    except ValueError as e:
        print(f"Error: {e}")
        return 1
    with open(salida, "wb") as f:
        f.write(datos)
    print(f"Listo: {salida} ({len(datos)} bytes). Contiene datos personales: guárdalo cifrado o bórralo al terminar.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
