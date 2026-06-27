# app.py
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import uuid
import json
import os
from datetime import datetime, timedelta
import random
import time

app = Flask(__name__)
app.secret_key = 'supersecretkey123'

# Store data in memory
quizzes = {}
controllers = {}
players = {}
game_states = {}

# Helper functions
def generate_id():
    return str(uuid.uuid4())[:8]

def get_domain():
    # Try to get domain from request, fallback to localhost
    if 'domain' in session and session['domain']:
        return session['domain']
    return request.host if request.host else 'localhost:5000'

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == 'lolxdlol':
            session['authenticated'] = True
            return redirect(url_for('dashboard'))
        return render_template('index.html', error='Złe hasło!')
    return render_template('index.html', error=None)

@app.route('/dashboard')
def dashboard():
    if not session.get('authenticated'):
        return redirect(url_for('index'))
    return render_template('dashboard.html')

@app.route('/create_quiz', methods=['POST'])
def create_quiz():
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    quiz_id = generate_id()
    
    # Store quiz data
    quizzes[quiz_id] = {
        'title': data.get('title'),
        'theme': data.get('theme'),
        'categories': data.get('categories', []),
        'questions': data.get('questions', {}),
        'created': datetime.now().isoformat()
    }
    
    # Generate shareable link
    domain = data.get('domain', get_domain())
    session['domain'] = domain
    link = f"{domain}/board/{quiz_id}"
    
    return jsonify({
        'success': True,
        'quiz_id': quiz_id,
        'link': link
    })

@app.route('/board/<quiz_id>')
def board(quiz_id):
    if quiz_id not in quizzes:
        return "Quiz not found", 404
    
    quiz = quizzes[quiz_id]
    controller_code = generate_id()
    controllers[controller_code] = {
        'quiz_id': quiz_id,
        'players': [],
        'game_state': 'waiting',  # waiting, countdown, active, finished
        'current_player': None,
        'current_question': None,
        'scores': {},
        'question_start': None
    }
    
    return render_template('board.html', 
                         quiz=quiz, 
                         quiz_id=quiz_id,
                         controller_code=controller_code,
                         domain=get_domain())

@app.route('/controller/<code>')
def controller(code):
    if code not in controllers:
        return "Controller not found", 404
    
    controller = controllers[code]
    quiz = quizzes[controller['quiz_id']]
    return render_template('controller.html', 
                         controller_code=code,
                         quiz=quiz,
                         controller=controller)

@app.route('/api/join', methods=['POST'])
def join_quiz():
    data = request.json
    code = data.get('code')
    name = data.get('name')
    avatar = data.get('avatar')
    
    if code not in controllers:
        return jsonify({'error': 'Invalid code'}), 404
    
    controller = controllers[code]
    player_id = generate_id()
    
    player = {
        'id': player_id,
        'name': name,
        'avatar': avatar,
        'score': 0,
        'device_id': data.get('device_id', str(uuid.uuid4()))
    }
    
    controller['players'].append(player)
    controller['scores'][player_id] = 0
    
    return jsonify({
        'success': True,
        'player_id': player_id,
        'quiz_id': controller['quiz_id']
    })

@app.route('/api/game/start_countdown', methods=['POST'])
def start_countdown():
    data = request.json
    code = data.get('code')
    
    if code not in controllers:
        return jsonify({'error': 'Invalid code'}), 404
    
    controller = controllers[code]
    controller['game_state'] = 'countdown'
    controller['countdown_start'] = datetime.now().isoformat()
    
    return jsonify({'success': True})

@app.route('/api/game/start', methods=['POST'])
def start_game():
    data = request.json
    code = data.get('code')
    
    if code not in controllers:
        return jsonify({'error': 'Invalid code'}), 404
    
    controller = controllers[code]
    controller['game_state'] = 'active'
    
    # Pick first player randomly
    if controller['players']:
        player = random.choice(controller['players'])
        controller['current_player'] = player['id']
    
    return jsonify({'success': True})

@app.route('/api/game/pick_player', methods=['POST'])
def pick_player():
    data = request.json
    code = data.get('code')
    
    if code not in controllers:
        return jsonify({'error': 'Invalid code'}), 404
    
    controller = controllers[code]
    
    # Pick random player from remaining
    available = [p for p in controller['players'] if p['id'] != controller.get('current_player')]
    if not available:
        available = controller['players']
    
    player = random.choice(available)
    controller['current_player'] = player['id']
    
    # Pick random category and question
    quiz = quizzes[controller['quiz_id']]
    categories = quiz['categories']
    category = random.choice(categories) if categories else None
    
    if category:
        questions = quiz['questions'].get(category, [])
        if questions:
            question = random.choice(questions)
            controller['current_question'] = {
                'category': category,
                'question': question
            }
            controller['question_start'] = datetime.now().isoformat()
    
    return jsonify({
        'success': True,
        'player': player,
        'category': category,
        'question': controller.get('current_question')
    })

@app.route('/api/game/answer', methods=['POST'])
def answer_question():
    data = request.json
    code = data.get('code')
    player_id = data.get('player_id')
    answer = data.get('answer')
    
    if code not in controllers:
        return jsonify({'error': 'Invalid code'}), 404
    
    controller = controllers[code]
    
    # Check if answer is correct (for demo, we'll just accept)
    # In real implementation, you'd check against stored answer
    if controller.get('current_player') == player_id:
        # Store the answer
        controller['current_answer'] = answer
        return jsonify({'success': True})
    
    return jsonify({'error': 'Not your turn'}), 403

@app.route('/api/game/score', methods=['POST'])
def update_score():
    data = request.json
    code = data.get('code')
    player_id = data.get('player_id')
    action = data.get('action')  # 'correct' or 'wrong'
    
    if code not in controllers:
        return jsonify({'error': 'Invalid code'}), 404
    
    controller = controllers[code]
    
    if player_id in controller['scores']:
        if action == 'correct':
            controller['scores'][player_id] += 5
        elif action == 'wrong':
            controller['scores'][player_id] -= 1
        
        return jsonify({
            'success': True,
            'new_score': controller['scores'][player_id]
        })
    
    return jsonify({'error': 'Player not found'}), 404

@app.route('/api/game/end', methods=['POST'])
def end_game():
    data = request.json
    code = data.get('code')
    
    if code not in controllers:
        return jsonify({'error': 'Invalid code'}), 404
    
    controller = controllers[code]
    controller['game_state'] = 'finished'
    
    # Get winner
    winner = max(controller['scores'], key=controller['scores'].get) if controller['scores'] else None
    
    return jsonify({
        'success': True,
        'winner': winner,
        'scores': controller['scores']
    })

@app.route('/api/game/state/<code>')
def get_game_state(code):
    if code not in controllers:
        return jsonify({'error': 'Invalid code'}), 404
    
    controller = controllers[code]
    quiz = quizzes[controller['quiz_id']]
    
    # Check if question time expired (60 seconds)
    if controller.get('question_start'):
        start = datetime.fromisoformat(controller['question_start'])
        if datetime.now() - start > timedelta(seconds=60):
            # Time's up, move to next player automatically
            pass
    
    return jsonify({
        'state': controller['game_state'],
        'players': controller['players'],
        'current_player': controller.get('current_player'),
        'current_question': controller.get('current_question'),
        'scores': controller['scores'],
        'quiz': quiz
    })

@app.route('/api/player/view/<quiz_id>')
def player_view(quiz_id):
    # For player mobile view
    return render_template('player.html', quiz_id=quiz_id)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
