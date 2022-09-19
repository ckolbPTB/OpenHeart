from flask import (
    Blueprint, render_template
)
from openheart.utils.utils import clean_up_user_files

bp = Blueprint('home', __name__, url_prefix='/home')


@bp.route('/', methods=['GET'])
def welcome():
    return render_template('home/welcome.html')


@bp.route('/finish', methods=['POST'])
def finish():
    clean_up_user_files()
    return render_template('home/welcome.html')


@bp.route('/tutorial_video', methods=['GET'])
def tutorial_video():
    return render_template('home/tutorial_video.html')


@bp.route('/ismrmrd_tools', methods=['GET'])
def ismrmrd_tools():
    return render_template('home/ismrmrd_tools.html')


@bp.route('/terms_conds', methods=['GET'])
def terms_conds():
    return render_template('home/terms_conds.html')
