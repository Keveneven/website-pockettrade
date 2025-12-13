"""
PokeTrade Flask Application - MVP Phase 2
Connects to your existing database schema
Run with: python app.py
"""

from flask import Flask, render_template, g, request, redirect, url_for, flash, session
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-prod')

DATABASE = 'poketrade.db'


# ============================================================
# DATABASE CONNECTION HELPERS
# ============================================================

def get_db():
    """Get a database connection, attach to Flask's `g` object."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    """Close the database connection on teardown."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False):
    """Helper function to query the database."""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    """Helper function to execute database commands."""
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    cur.close()


# ============================================================
# AUTH HELPERS
# ============================================================

def get_current_user():
    """Return the currently logged-in user row or None."""
    if 'user_id' not in session:
        return None
    return query_db('SELECT * FROM users WHERE id = ?', [session['user_id']], one=True)


# ============================================================
# HOMEPAGE (uses templates/index.html)
# ============================================================

@app.route('/')
def index():
    """Homepage with market overview and recent activity"""
    total_cards = query_db('SELECT COUNT(*) as count FROM cards', one=True)['count']
    active_listings = query_db(
        "SELECT COUNT(*) as count FROM listings WHERE status = 'active'",
        one=True
    )['count']
    upcoming_events = query_db(
        'SELECT COUNT(*) as count FROM events WHERE start_datetime >= datetime("now")',
        one=True
    )['count']
    active_users = query_db(
        'SELECT COUNT(*) as count FROM users',
        one=True
    )['count']

    listings = query_db('''
        SELECT 
            listings.*,
            cards.name as card_name,
            cards.card_number,
            cards.image_url,
            sets.name as set_name,
            users.username
        FROM listings
        JOIN cards ON listings.card_id = cards.id
        JOIN sets ON cards.set_id = sets.id
        JOIN users ON listings.user_id = users.id
        WHERE listings.status = 'active'
        ORDER BY listings.created_at DESC
        LIMIT 6
    ''')

    events = query_db('''
        SELECT 
            events.*,
            COUNT(event_attendance.id) as attendee_count
        FROM events
        LEFT JOIN event_attendance ON events.id = event_attendance.event_id
        WHERE events.start_datetime >= datetime("now")
        GROUP BY events.id
        ORDER BY events.start_datetime
        LIMIT 6
    ''')

    return render_template(
        'index.html',
        total_cards=total_cards,
        active_listings=active_listings,
        upcoming_events=upcoming_events,
        active_users=active_users,
        listings=listings,
        events=events
    )


# ============================================================
# CARD LIBRARY (templates/cards.html)
# ============================================================

@app.route('/cards')
def cards():
    """Browse all cards with search and filtering"""
    search = request.args.get('search', '')
    set_filter = request.args.get('set', '')

    query = '''
        SELECT 
            cards.*,
            sets.name as set_name,
            (SELECT MIN(price) FROM listings 
             WHERE card_id = cards.id AND status = 'active') as floor_price,
            (SELECT COUNT(*) FROM user_cards 
             WHERE card_id = cards.id AND list_type = 'want') as want_count,
            (SELECT COUNT(*) FROM user_cards 
             WHERE card_id = cards.id AND list_type = 'have') as have_count
        FROM cards
        JOIN sets ON cards.set_id = sets.id
        WHERE 1=1
    '''

    params = []

    if search:
        query += ' AND cards.name LIKE ?'
        params.append(f'%{search}%')

    if set_filter:
        query += ' AND sets.id = ?'
        params.append(set_filter)

    query += ' ORDER BY cards.name ASC'

    cards_list = query_db(query, params)
    sets_list = query_db('SELECT * FROM sets ORDER BY name')

    return render_template('cards.html', cards=cards_list, sets=sets_list)


# ============================================================
# CARD DETAIL (templates/card_detail.html)
# ============================================================

@app.route('/cards/<int:card_id>')
def card_detail(card_id):
    """Detailed view of a single card"""
    card = query_db('''
        SELECT 
            cards.*,
            sets.name as set_name
        FROM cards
        JOIN sets ON cards.set_id = sets.id
        WHERE cards.id = ?
    ''', [card_id], one=True)

    if not card:
        flash('Card not found', 'error')
        return redirect(url_for('cards'))

    listings = query_db('''
        SELECT 
            listings.*,
            users.username
        FROM listings
        JOIN users ON listings.user_id = users.id
        WHERE listings.card_id = ? AND listings.status = 'active'
        ORDER BY listings.price ASC
    ''', [card_id])

    haves = query_db('''
        SELECT 
            users.username
        FROM user_cards
        JOIN users ON user_cards.user_id = users.id
        WHERE user_cards.card_id = ? AND user_cards.list_type = 'have'
    ''', [card_id])

    wants = query_db('''
        SELECT 
            users.username
        FROM user_cards
        JOIN users ON user_cards.user_id = users.id
        WHERE user_cards.card_id = ? AND user_cards.list_type = 'want'
    ''', [card_id])

    return render_template(
        'card_detail.html',
        card=card,
        listings=listings,
        haves=haves,
        wants=wants
    )


# ============================================================
# LISTINGS (templates/listings.html)
# ============================================================

@app.route('/listings')
def listings():
    """View all active listings"""
    all_listings = query_db('''
        SELECT 
            listings.*,
            cards.name as card_name,
            cards.image_url,
            sets.name as set_name,
            users.username
        FROM listings
        JOIN cards ON listings.card_id = cards.id
        JOIN sets ON cards.set_id = sets.id
        JOIN users ON listings.user_id = users.id
        WHERE listings.status = 'active'
        ORDER BY listings.created_at DESC
    ''')

    return render_template('listings.html', listings=all_listings)


# ============================================================
# EVENTS (templates/events.html + event_detail.html)
# ============================================================

@app.route('/events')
def events():
    """View all events"""
    all_events = query_db('''
        SELECT 
            events.*,
            COUNT(DISTINCT event_attendance.id) as attendee_count,
            COUNT(DISTINCT event_cards.id) as cards_count
        FROM events
        LEFT JOIN event_attendance ON events.id = event_attendance.event_id
        LEFT JOIN event_cards ON events.id = event_cards.event_id
        GROUP BY events.id
        ORDER BY events.start_datetime
    ''')

    return render_template('events.html', events=all_events)


@app.route('/events/<int:event_id>')
def event_detail(event_id):
    """Detailed event view with attendees and cards"""
    event = query_db('SELECT * FROM events WHERE id = ?', [event_id], one=True)

    if not event:
        flash('Event not found', 'error')
        return redirect(url_for('events'))

    attendees = query_db('''
        SELECT users.username, users.location_city, 
               event_attendance.role, event_attendance.status
        FROM event_attendance
        JOIN users ON event_attendance.user_id = users.id
        WHERE event_attendance.event_id = ?
    ''', [event_id])

    cards_at_event = query_db('''
        SELECT event_cards.*, cards.name, cards.image_url, users.username
        FROM event_cards
        JOIN cards ON event_cards.card_id = cards.id
        JOIN users ON event_cards.user_id = users.id
        WHERE event_cards.event_id = ?
    ''', [event_id])

    return render_template(
        'event_detail.html',
        event=event,
        attendees=attendees,
        cards_at_event=cards_at_event
    )


# ============================================================
# BINDERS (templates/binders.html + user_binder.html)
# ============================================================

@app.route('/binders')
def binders():
    """View all public user binders"""
    users_list = query_db('''
        SELECT 
            users.*,
            COUNT(DISTINCT CASE WHEN user_cards.list_type = 'have' THEN user_cards.id END) as have_count,
            COUNT(DISTINCT CASE WHEN user_cards.list_type = 'want' THEN user_cards.id END) as want_count,
            COUNT(DISTINCT listings.id) as listing_count
        FROM users
        LEFT JOIN user_cards ON users.id = user_cards.user_id
        LEFT JOIN listings ON users.id = listings.user_id 
                            AND listings.status = 'active'
        GROUP BY users.id
        ORDER BY have_count DESC
    ''')

    return render_template('binders.html', users=users_list)


@app.route('/binders/<username>')
def user_binder(username):
    """View a specific user's binder"""
    user = query_db('SELECT * FROM users WHERE username = ?', [username], one=True)

    if not user:
        flash('User not found', 'error')
        return redirect(url_for('binders'))

    haves = query_db('''
        SELECT user_cards.*, cards.name, cards.image_url, sets.name as set_name
        FROM user_cards
        JOIN cards ON user_cards.card_id = cards.id
        JOIN sets ON cards.set_id = sets.id
        WHERE user_cards.user_id = ? AND user_cards.list_type = 'have'
        ORDER BY cards.name
    ''', [user['id']])

    wants = query_db('''
        SELECT user_cards.*, cards.name, cards.image_url, sets.name as set_name
        FROM user_cards
        JOIN cards ON user_cards.card_id = cards.id
        JOIN sets ON cards.set_id = sets.id
        WHERE user_cards.user_id = ? AND user_cards.list_type = 'want'
        ORDER BY cards.name
    ''', [user['id']])

    listings = query_db('''
        SELECT listings.*, cards.name as card_name, 
               cards.image_url, sets.name as set_name
        FROM listings
        JOIN cards ON listings.card_id = cards.id
        JOIN sets ON cards.set_id = sets.id
        WHERE listings.user_id = ? AND listings.status = 'active'
        ORDER BY listings.created_at DESC
    ''', [user['id']])

    return render_template(
        'user_binder.html',
        user=user,
        haves=haves,
        wants=wants,
        listings=listings
    )


# ============================================================
# AUTH (templates/login.html + register.html)
# ============================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = query_db('SELECT * FROM users WHERE username = ?', [username], one=True)

        if not user or not check_password_hash(user['password_hash'], password):
            flash('Invalid username or password', 'error')
        else:
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Logged in successfully', 'success')
            return redirect(url_for('index'))

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        existing = query_db(
            'SELECT * FROM users WHERE username = ?', [username],
            one=True
        )
        if existing:
            flash('Username already taken', 'error')
        else:
            password_hash = generate_password_hash(password)
            execute_db(
                'INSERT INTO users (username, password_hash) VALUES (?, ?)',
                [username, password_hash]
            )
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
def logout():
    """Log the user out"""
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))


# ============================================================
# MY BINDER (templates/my_binder.html)
# ============================================================

@app.route('/my-binder')
def my_binder():
    """View logged-in user's personal binder"""
    if 'user_id' not in session:
        flash('Please login to view your binder', 'error')
        return redirect(url_for('login'))

    haves = query_db('''
        SELECT user_cards.*, cards.name, cards.image_url, sets.name as set_name
        FROM user_cards
        JOIN cards ON user_cards.card_id = cards.id
        JOIN sets ON cards.set_id = sets.id
        WHERE user_cards.user_id = ? AND user_cards.list_type = 'have'
        ORDER BY cards.name
    ''', [session['user_id']])

    wants = query_db('''
        SELECT user_cards.*, cards.name, cards.image_url, sets.name as set_name
        FROM user_cards
        JOIN cards ON user_cards.card_id = cards.id
        JOIN sets ON cards.set_id = sets.id
        WHERE user_cards.user_id = ? AND user_cards.list_type = 'want'
        ORDER BY cards.name
    ''', [session['user_id']])

    return render_template(
        'my_binder.html',
        haves=haves,
        wants=wants
    )


# ============================================================
# APP ENTRYPOINT
# ============================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
