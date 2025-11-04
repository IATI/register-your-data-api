import os

from sqlmodel import SQLModel, create_engine


def setup_db(db_conn: str) -> None:
    if db_conn.startswith("sqlite://"):
        db_file = db_conn.replace("sqlite:///", "")
        if os.path.isfile(db_file):
            os.unlink(db_file)
    print("Created database in setup_db() for test...")
    engine = create_engine(db_conn, echo=True)
    SQLModel.metadata.create_all(engine)
