from flask import Blueprint, render_template, current_app as app

bp_main = Blueprint("main", __name__)

@bp_main.route("/")
def index():
    return render_template("index.html", v=app.config.get("START_TIME", "dev"))

@bp_main.route("/farm")
def farm():
    return render_template("farm.html", v=app.config.get("START_TIME", "dev"))

@bp_main.route("/admin/testing/tools")
def dev_tools():
    return render_template("dev_tools.html", v=app.config.get("START_TIME", "dev"))

@bp_main.route("/blocked")
def blocked():
    return render_template("blocked.html", v=app.config.get("START_TIME", "dev"))
