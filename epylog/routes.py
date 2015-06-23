from flask import Flask, render_template, make_response
from sqlalchemy import desc, func, and_, or_
import pygal

import datetime

from .model import Player, Game, Weapon, db_session, Kill


app = Flask(__name__)
app.config.from_object(__name__)

COLORS = {
    '^0': '#000000',
    '^1': '#FF0000',
    '^2': '#00FF00',
    '^3': '#FFFF00',
    '^4': '#0000FF',
    '^5': '#00FFFF',
    '^6': '#FF00FF',
    '^7': '#FFFFFF'}


@app.template_filter('process_color')
def process_color(pseudo):
    """Interpret the special characters in players pseudo as display colors.
    """
    for key, color in COLORS.items():
        pseudo = pseudo.replace(key, '<span style="color:{}">'.format(color))
    return pseudo + pseudo.count('<span') * '</span>'


@app.route('/')
def home_page():
    sorted_players = sorted(
        Player.query.all(), key=lambda p: p.ratio_kill_killed(), reverse=True)
    game_history = Game.query.order_by(desc(Game.ending_time)).limit(5)
    return render_template(
        'home_page.html', top_players=sorted_players[:3],
        game_history=game_history)


@app.route('/playerslist')
def show_players_list():
    sorted_players = sorted(
        Player.query.all(), key=lambda p: p.ratio_kill_killed(), reverse=True)
    return render_template('player_list.html', top_players=sorted_players)


@app.route('/playerdetails/<pseudo>')
def show_player_details(pseudo):
    player = Player.query.filter_by(pseudo=pseudo).first()
    return render_template(
            'player_details.html',
            player=player,
            actual_date=datetime.datetime.now())


@app.route('/weapongraph/<pseudo>.svg')
def generate_weapon_graph(pseudo):
    radar_chart = pygal.Radar()
    radar_chart.title = 'Weapon use'
    labels = []
    values = []
    for row in Player.query.filter_by(pseudo=pseudo).first().weapon_statistics:
        labels.append(Weapon.query.get(row.weapon_id).weapon_name)
        values.append(row.kill_count)
    radar_chart.x_labels = labels
    radar_chart.add('Weapon use', values)
    response = make_response(radar_chart.render())
    response.content_type = 'image/svg+xml'
    return response


@app.route('/ratiograph/<pseudo>.svg')
def generate_ratio_graph(pseudo):
    player = Player.query.filter_by(pseudo=pseudo).first()
    labels = []
    values = []
    games = (
        db_session
        .query(Kill.game_id)
        .filter(or_(
            Kill.player_killer_id == player.id,
            Kill.player_killed_id == player.id))
        .group_by(Kill.game_id)
        .all())
    for row in games:
        game = Game.query.get(row.game_id)
        labels.append(str(game.ending_time))
        values.append(player.ratio_kill_killed(game.ending_time))
    line_chart = pygal.Line()
    line_chart.title = 'Ratio evolution'
    line_chart.x_labels = labels
    line_chart.add('Ratio k/k', values)
    response = make_response(line_chart.render())
    response.content_type = 'image/svg+xml'
    return response


@app.route('/gamehistory')
def show_game_history():
    game_history = Game.query.order_by(desc(Game.ending_time))
    return render_template('game_history.html', game_history=game_history)


@app.route('/weapons')
def show_weapon_statistics():
    weapon_list = (
        db_session.query(
            Weapon.weapon_name.label('weapon_name'),
            func.count(Weapon.weapon_name).label('count'))
        .join(Weapon.kills)
        .filter(Kill.player_killer_id != Kill.player_killed_id)
        .group_by(Weapon.weapon_name)
        .subquery())
    kill_weapon_player = (
        db_session.query(
            Kill.weapon_id.label('weapon_id'),
            Kill.player_killer_id.label('player_killer_id'),
            func.count(Kill.weapon_id).label('count'))
        .filter(Kill.player_killer_id != Kill.player_killed_id)
        .group_by(Kill.weapon_id, Kill.player_killer_id)
        .subquery())
    best_kill_weapon = (
        db_session.query(
            kill_weapon_player.c.weapon_id.label('weapon_id'),
            func.max(kill_weapon_player.c.count).label('maxi'))
        .group_by(kill_weapon_player.c.weapon_id)
        .subquery())

    best_player_weapon = (
        db_session.query(
            best_kill_weapon.c.maxi.label('kill'),
            Player.pseudo.label('pseudo'),
            Weapon.weapon_name.label('weapon'),
            weapon_list.c.count.label('total'))
        .join(kill_weapon_player, and_(
            kill_weapon_player.c.weapon_id == best_kill_weapon.c.weapon_id,
            kill_weapon_player.c.count == best_kill_weapon.c.maxi))
        .join(Weapon, Weapon.id == kill_weapon_player.c.weapon_id)
        .join(Player, Player.id == kill_weapon_player.c.player_killer_id)
        .join(weapon_list, weapon_list.c.weapon_name == Weapon.weapon_name))
    return render_template(
        'weapons.html', best_player_weapon=best_player_weapon)


@app.route('/weapons/weapon_graph.svg')
def generate_all_weapons_graph():
    bar_diag = pygal.HorizontalBar()
    bar_diag.title = 'Total weapon kills'
    weapon_list = (
        db_session.query(
            Weapon.weapon_name,
            func.count(Weapon.weapon_name).label('count'))
        .join(Weapon.kills)
        .filter(Kill.player_killer_id != Kill.player_killed_id)
        .group_by(Weapon.weapon_name)
        .order_by(func.count(Weapon.weapon_name)))
    for weapon in weapon_list:
        bar_diag.add(weapon.weapon_name, weapon.count)
    response = make_response(bar_diag.render())
    response.content_type = 'image/svg+xml'
    return response
