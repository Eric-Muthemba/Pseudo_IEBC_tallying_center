from flask.cli import FlaskGroup
from server import db, create_app

app = create_app()
app.app_context().push()

cli = FlaskGroup(app)


@cli.command("create_db")
def create_db():
    db.drop_all()
    db.create_all()
    db.session.commit()


if __name__ == "__main__":
    cli()