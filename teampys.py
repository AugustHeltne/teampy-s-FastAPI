from .classes import RAT, Card
from flask import Flask
from flask import request
from flask import redirect
from flask import render_template
import uuid
import random
import string
from flask_pymongo import PyMongo

app = Flask(__name__)

app.config['SECRET_KEY'] = 'Hemmelig!'  # is required
app.config["MONGO_DBNAME"] = "ratdb"  # DB name
app.config["MONGO_URI"] = "mongodb://localhost:27017/ratdb"

mongo = PyMongo(app)
ratdb = mongo.db.ratdb

colors = ['STEELBLUE', 'CADETBLUE', 'LIGHTSEAGREEN', 'OLIVEDRAB',
          'YELLOWGREEN', 'FORESTGREEN', 'MEDIUMSEAGREEN', 'LIGHTGREEN',
          'LIMEGREEN', 'DARKMAGENTA', 'DARKORCHID', 'MEDIUMORCHID', 'ORCHID',
          'ORANGE', 'ORANGERED', 'CORAL', 'LIGHTSALMON', 'PALEVIOLETRED',
          'MEDIUMVIOLETRED', 'DEEPPINK', 'CRIMSON', 'SALMON']

# all scratchcards
cards = {}
# teacher UUID to RAT
rats_by_private_id = {}
# student access to RAT
rats_by_public_id = {}

use_variables = False


def find_rat_by_public_id(public_id):
    if use_variables:
        global rats_by_public_id
        if public_id in rats_by_public_id:
            return RAT.from_dict(rats_by_public_id[public_id])
    else:
        data = ratdb.find_one({'public_id': public_id})
        if data:
            return RAT.from_dict(data)
    return None


def find_rat_by_private_id(private_id):
    if use_variables:
        global rats_by_private_id
        if private_id in rats_by_private_id:
            d = rats_by_private_id[private_id]
            return RAT.from_dict(d)
    else:
        data = ratdb.find_one({'private_id': private_id})
        if data:
            return RAT.from_dict(data)
    return None


def store_rat(rat):
    data = rat.to_dict()
    if use_variables:
        global rats_by_private_id
        global rats_by_public_id
        rats_by_private_id[rat.private_id] = data
        rats_by_public_id[rat.public_id] = data
    else:
        ratdb.replace_one({'private_id': rat.private_id}, data, upsert=True)


def find_card_by_id(card_id):
    if use_variables:
        global cards
        if card_id in cards:
            return Card.from_dict(cards[card_id])
    else:
        data = ratdb.find_one({'id': card_id})
        if data:
            return Card.from_dict(data)
    return None


def store_card(card):
    data = card.to_dict()
    if use_variables:
        global cards
        cards[card.id] = data
    else:
        ratdb.replace_one({'id': card.id}, data, upsert=True)


@app.route('/')
def index():
    action_url = request.host_url + 'join'
    return render_template('start.html', primary='#007bff', action_url=action_url)


def return_student_page(public_id):
    rat = find_rat_by_public_id(public_id)
    if rat is None:
        return "Could not find rat."
    else:
        return rat.html_students(request.host_url)


@app.route('/join', methods=['POST', 'GET'])
def join():
    rat = request.args['rat']
    return return_student_page(rat)


@app.route('/rat/<public_id>/')
def show_rat_students(public_id):
    return return_student_page(public_id)


@app.route('/new/', methods=['POST', 'GET'])
def new():
    action_url = request.host_url + 'create'
    return render_template('new_rat.html', primary='#007bff', action_url=action_url)


def validate_solution(solution, questions, alternatives):
    valid_alternatives = 'ABCDDEFGH'[:alternatives]
    if len(solution) != questions:
        return 'You specified {} questions, but provided {} solution alternatives.'.format(questions, len(solution))
    for c in solution.upper():
        if c not in valid_alternatives:
            return 'The letter {} is not a valid solution with {} alternatives.'.format(c, alternatives)
    return None  # all okay


@app.route('/create', methods=['POST', 'GET'])
def create():
    label = request.args['label'] if 'label' in request.args else None
    teams = int(request.args['teams'])
    questions = int(request.args['questions'])
    alternatives = int(request.args['alternatives'])
    solution = request.args['solution']
    message = validate_solution(solution, questions, alternatives)
    if message is not None:
        return message
    app.logger.debug(
        'Create new RAT label: {}, teams: {}, questions: {}, alternatives: {}, solution: {}'.format(label, teams,
                                                                                                    questions,
                                                                                                    alternatives,
                                                                                                    solution))
    private_id = '{}'.format(uuid.uuid4())
    public_id = ''.join(random.choices(string.ascii_uppercase, k=5))
    team_colors = random.sample(colors, teams)
    rat = RAT(private_id, public_id, label, teams, questions, alternatives, solution, team_colors)
    # create a new card for each team
    for team in range(1, int(teams) + 1, 1):
        card = Card.new_card(label, str(team), int(questions), int(alternatives), solution, rat.team_colors[team - 1])
        store_card(card)
        rat.card_ids_by_team[str(team)] = card.id
    store_rat(rat)
    return redirect("../teacher/{}".format(rat.private_id), code=302)


@app.route('/teacher/<private_id>/')
def show_rat_teacher(private_id):
    rat = find_rat_by_private_id(private_id)
    if rat is None:
        return "Could not find rat."
    rat_cards = []
    for card_id in rat.card_ids_by_team.values():
        card = find_card_by_id(card_id)
        if card is not None:
            rat_cards.append(card)
    return rat.html_teacher(request.host_url, rat_cards)


@app.route('/card/<id>/')
def show_card(id):
    card = find_card_by_id(id)
    if card is None:
        return "Could not find card."
    # check if the page request also answers a question
    if 'question' in request.form:  # and ('alternative' in request.form):
        question = request.form['question']
        alternative = request.form['alternative']
        card.uncover(question, alternative)
    if 'question' in request.args:  # and ('alternative' in request.form):
        question = request.args['question']
        alternative = request.args['alternative']
        card.uncover(question, alternative)
    store_card(card)
    return card.get_card_html(request.host_url)


@app.route('/grab/<public_id>/<team>')
def grab_rat_students(public_id, team):
    rat = find_rat_by_public_id(public_id)
    if rat is None:
        return "Could not find RAT."
    card_id = rat.grab(team)
    if card_id is None:
        return 'Somebody already grabbed that card.'
    card = find_card_by_id(card_id)
    if card is None:
        return "Could not find card with ID {}".format(card_id)
    store_rat(rat)
    return redirect("../../card/{}".format(card_id), code=302)


@app.route('/download/<private_id>/<format>/')
def download(private_id, format):
    rat = find_rat_by_private_id(private_id)
    if rat is None:
        return "Could not find RAT."
    rat_cards = []
    for card_id in rat.card_ids_by_team.values():
        card = find_card_by_id(card_id)
        if card is not None:
            rat_cards.append(card)
    return rat.download(format, rat_cards)
