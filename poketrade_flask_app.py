"""
PokeTrade Flask Application - MVP Phase 2
Connects to your existing database schema
Run with: python app.py
"""

from flask import Flask, render_template_string, g, request, redirect, url_for, flash, session
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
DATABASE = 'poketrade.db'

# ============================================================
# DATABASE HELPERS
# ============================================================

def get_db():
    """Get database connection with foreign keys enabled"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
    return db

@app.teardown_appcontext
def close_connection(exception):
    """Close database connection after each request"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    """Execute SELECT query"""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    """Execute INSERT/UPDATE/DELETE query"""
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    return cur.lastrowid

# ============================================================
# BASE TEMPLATE
# ============================================================

BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}PokeTrade{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50">
    <!-- Navigation -->
    <nav class="bg-blue-600 text-white shadow-lg">
        <div class="container mx-auto px-4 py-4">
            <div class="flex items-center justify-between">
                <a href="/" class="text-2xl font-bold">PokeTrade</a>
                <div class="flex items-center space-x-6">
                    <a href="/cards" class="hover:underline">Cards</a>
                    <a href="/listings" class="hover:underline">Listings</a>
                    <a href="/events" class="hover:underline">Events</a>
                    <a href="/binders" class="hover:underline">Binders</a>
                    {% if session.get('user_id') %}
                        <a href="/my-binder" class="hover:underline font-semibold">My Binder</a>
                        <a href="/logout" class="hover:underline">Logout ({{ session.get('username') }})</a>
                    {% else %}
                        <a href="/login" class="bg-white text-blue-600 px-4 py-2 rounded hover:bg-gray-100">Login</a>
                    {% endif %}
                </div>
            </div>
        </div>
    </nav>

    <!-- Flash Messages -->
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            <div class="container mx-auto px-4 mt-4">
                {% for category, message in messages %}
                    <div class="bg-{% if category == 'error' %}red{% else %}green{% endif %}-100 border border-{% if category == 'error' %}red{% else %}green{% endif %}-400 text-{% if category == 'error' %}red{% else %}green{% endif %}-700 px-4 py-3 rounded mb-4">
                        {{ message }}
                    </div>
                {% endfor %}
            </div>
        {% endif %}
    {% endwith %}

    {% block base_content %}{% endblock %}

    <!-- Footer -->
    <footer class="bg-gray-800 text-white py-8 mt-12">
        <div class="container mx-auto px-4 text-center">
            <p class="mb-2">PokeTrade - The TCG Intelligence Hub</p>
            <p class="text-sm text-gray-400">Market data • Collections • Events • All in one place</p>
            <p class="text-xs text-gray-500 mt-4">MVP Phase 2 - Using Your Schema</p>
        </div>
    </footer>
</body>
</html>
"""

# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def index():
    """Homepage with market overview and recent activity"""
    # Get stats
    total_cards = query_db('SELECT COUNT(*) as count FROM cards', one=True)['count']
    active_listings = query_db("SELECT COUNT(*) as count FROM listings WHERE status = 'active'", one=True)['count']
    upcoming_events = query_db('SELECT COUNT(*) as count FROM events WHERE start_datetime >= datetime("now")', one=True)['count']
    active_users = query_db('SELECT COUNT(*) as count FROM users', one=True)['count']
    
    # Get recent listings with card details
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
    
    # Get upcoming events
    events = query_db('''
        SELECT 
            events.*,
            COUNT(event_attendance.id) as attendee_count
        FROM events
        LEFT JOIN event_attendance ON events.id = event_attendance.event_id
        WHERE events.start_datetime >= datetime("now")
        GROUP BY events.id
        ORDER BY events.start_datetime
        LIMIT 3
    ''')
    
    template = BASE_TEMPLATE + """
    {% block content %}
    <!-- Hero Section -->
    <div class="bg-gradient-to-r from-blue-500 to-purple-600 text-white py-16">
        <div class="container mx-auto px-4 text-center">
            <h2 class="text-4xl font-bold mb-4">The TCG Intelligence Hub</h2>
            <p class="text-xl mb-8">Track collections, discover listings, find events—all in one place</p>
            {% if not session.get('user_id') %}
            <div class="flex justify-center gap-4">
                <a href="/register" class="bg-white text-blue-600 px-6 py-3 rounded-lg font-semibold hover:bg-gray-100">
                    Sign Up Free
                </a>
                <a href="/cards" class="border-2 border-white px-6 py-3 rounded-lg font-semibold hover:bg-white hover:text-blue-600">
                    Browse Cards
                </a>
            </div>
            {% endif %}
        </div>
    </div>

    <div class="container mx-auto px-4 py-8">
        <!-- Stats -->
        <section class="mb-12">
            <h3 class="text-3xl font-bold mb-6">Market Overview</h3>
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div class="bg-white p-6 rounded-lg shadow">
                    <div class="text-gray-500 text-sm">Total Cards</div>
                    <div class="text-3xl font-bold">{{ total_cards }}</div>
                </div>
                <div class="bg-white p-6 rounded-lg shadow">
                    <div class="text-gray-500 text-sm">Active Listings</div>
                    <div class="text-3xl font-bold">{{ active_listings }}</div>
                </div>
                <div class="bg-white p-6 rounded-lg shadow">
                    <div class="text-gray-500 text-sm">Upcoming Events</div>
                    <div class="text-3xl font-bold">{{ upcoming_events }}</div>
                </div>
                <div class="bg-white p-6 rounded-lg shadow">
                    <div class="text-gray-500 text-sm">Active Users</div>
                    <div class="text-3xl font-bold">{{ active_users }}</div>
                </div>
            </div>
        </section>

        <!-- Recent Listings -->
        {% if listings %}
        <section class="mb-12">
            <h3 class="text-3xl font-bold mb-6">Recent Listings</h3>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {% for listing in listings %}
                <div class="bg-white rounded-lg shadow-lg overflow-hidden hover:shadow-xl transition-shadow">
                    {% if listing.image_url %}
                    <img src="{{ listing.image_url }}" alt="{{ listing.card_name }}" class="w-full h-64 object-contain bg-gray-100 p-4">
                    {% else %}
                    <div class="w-full h-64 bg-gray-200 flex items-center justify-center">
                        <span class="text-gray-400">No Image</span>
                    </div>
                    {% endif %}
                    <div class="p-4">
                        <div class="flex justify-between items-start mb-2">
                            <div>
                                <h4 class="font-bold text-lg">{{ listing.card_name }}</h4>
                                <p class="text-sm text-gray-600">{{ listing.set_name }} #{{ listing.card_number }}</p>
                            </div>
                            {% if listing.condition %}
                            <span class="bg-yellow-100 text-yellow-800 text-xs px-2 py-1 rounded">{{ listing.condition }}</span>
                            {% endif %}
                        </div>
                        <div class="flex justify-between items-center mt-4">
                            <span class="text-2xl font-bold text-green-600">${{ "%.2f"|format(listing.price) }}</span>
                            <span class="text-sm text-gray-500">by {{ listing.username }}</span>
                        </div>
                        {% if listing.description %}
                        <p class="text-sm text-gray-600 mt-2">{{ listing.description[:100] }}{% if listing.description|length > 100 %}...{% endif %}</p>
                        {% endif %}
                        <a href="/cards/{{ listing.card_id }}" class="block w-full mt-4 bg-blue-600 text-white py-2 rounded hover:bg-blue-700 text-center">
                            View Card
                        </a>
                    </div>
                </div>
                {% endfor %}
            </div>
        </section>
        {% endif %}

        <!-- Upcoming Events -->
        {% if events %}
        <section class="mb-12">
            <h3 class="text-3xl font-bold mb-6">Upcoming Events</h3>
            <div class="space-y-4">
                {% for event in events %}
                <div class="bg-white p-6 rounded-lg shadow hover:shadow-lg transition-shadow">
                    <div class="flex justify-between items-start">
                        <div>
                            <h4 class="text-xl font-bold mb-2">{{ event.name }}</h4>
                            <p class="text-gray-600 mb-2">📍 {{ event.location_venue }}{% if event.location_city %}, {{ event.location_city }}, {{ event.location_region }}{% endif %}</p>
                            <p class="text-gray-600 mb-4">📅 {{ event.start_datetime[:10] }}</p>
                            {% if event.description %}
                            <p class="text-sm text-gray-700">{{ event.description }}</p>
                            {% endif %}
                            <div class="mt-4">
                                <span class="text-sm font-semibold">{{ event.attendee_count }} collectors attending</span>
                            </div>
                        </div>
                        <a href="/events/{{ event.id }}" class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
                            View Event
                        </a>
                    </div>
                </div>
                {% endfor %}
            </div>
        </section>
        {% endif %}
    </div>
    {% endblock %}
    """
    
    return render_template_string(template, 
        total_cards=total_cards,
        active_listings=active_listings,
        upcoming_events=upcoming_events,
        active_users=active_users,
        listings=listings,
        events=events
    )

@app.route('/cards')
def cards():
    """Browse all cards with search and filtering"""
    search = request.args.get('search', '')
    set_filter = request.args.get('set', '')
    
    query = '''
        SELECT 
            cards.*,
            sets.name as set_name,
            sets.series,
            COUNT(DISTINCT uc_have.id) as have_count,
            COUNT(DISTINCT uc_want.id) as want_count,
            MIN(listings.price) as floor_price
        FROM cards
        JOIN sets ON cards.set_id = sets.id
        LEFT JOIN user_cards uc_have ON cards.id = uc_have.card_id AND uc_have.list_type = 'have'
        LEFT JOIN user_cards uc_want ON cards.id = uc_want.card_id AND uc_want.list_type = 'want'
        LEFT JOIN listings ON cards.id = listings.card_id AND listings.status = 'active'
    '''
    
    conditions = []
    params = []
    
    if search:
        conditions.append("cards.name LIKE ?")
        params.append(f'%{search}%')
    
    if set_filter:
        conditions.append("sets.id = ?")
        params.append(set_filter)
    
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    
    query += ' GROUP BY cards.id ORDER BY cards.name'
    
    cards_list = query_db(query, params)
    sets_list = query_db('SELECT * FROM sets ORDER BY name')
    
    template = BASE_TEMPLATE + """
    {% block content %}
    <div class="container mx-auto px-4 py-8">
        <h2 class="text-3xl font-bold mb-6">Card Library</h2>
        
        <!-- Search/Filter -->
        <div class="bg-white p-6 rounded-lg shadow mb-8">
            <form method="GET" class="flex gap-4">
                <input type="text" name="search" placeholder="Search cards..." 
                    value="{{ request.args.get('search', '') }}"
                    class="flex-1 px-4 py-2 border rounded">
                <select name="set" class="px-4 py-2 border rounded">
                    <option value="">All Sets</option>
                    {% for set in sets %}
                    <option value="{{ set.id }}" {% if request.args.get('set') == set.id|string %}selected{% endif %}>
                        {{ set.name }}
                    </option>
                    {% endfor %}
                </select>
                <button type="submit" class="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700">
                    Search
                </button>
            </form>
        </div>

        <!-- Cards Grid -->
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {% for card in cards %}
            <a href="/cards/{{ card.id }}" class="bg-white rounded-lg shadow hover:shadow-lg transition-shadow overflow-hidden">
                {% if card.image_url %}
                <img src="{{ card.image_url }}" alt="{{ card.name }}" class="w-full aspect-[2.5/3.5] object-contain bg-gray-100">
                {% else %}
                <div class="w-full aspect-[2.5/3.5] bg-gray-200 flex items-center justify-center">
                    <span class="text-gray-400 text-sm">No Image</span>
                </div>
                {% endif %}
                <div class="p-3">
                    <h4 class="font-bold text-sm truncate">{{ card.name }}</h4>
                    <p class="text-xs text-gray-600">{{ card.set_name }}</p>
                    {% if card.floor_price %}
                    <p class="text-sm font-bold text-green-600 mt-2">${{ "%.2f"|format(card.floor_price) }}</p>
                    {% endif %}
                    <div class="flex justify-between text-xs text-gray-500 mt-2">
                        <span>{{ card.have_count }} have</span>
                        <span>{{ card.want_count }} want</span>
                    </div>
                </div>
            </a>
            {% endfor %}
        </div>
    </div>
    {% endblock %}
    """
    
    return render_template_string(template, cards=cards_list, sets=sets_list)

@app.route('/cards/<int:card_id>')
def card_detail(card_id):
    """Detailed view of a single card with market intelligence"""
    card = query_db('''
        SELECT cards.*, sets.name as set_name, sets.series
        FROM cards
        JOIN sets ON cards.set_id = sets.id
        WHERE cards.id = ?
    ''', [card_id], one=True)
    
    if not card:
        flash('Card not found', 'error')
        return redirect(url_for('cards'))
    
    # Get active listings
    listings = query_db('''
        SELECT listings.*, users.username, users.location_city, users.location_region
        FROM listings
        JOIN users ON listings.user_id = users.id
        WHERE listings.card_id = ? AND listings.status = 'active'
        ORDER BY listings.price
    ''', [card_id])
    
    # Get public haves
    haves = query_db('''
        SELECT user_cards.*, users.username
        FROM user_cards
        JOIN users ON user_cards.user_id = users.id
        WHERE user_cards.card_id = ? AND user_cards.list_type = 'have' AND user_cards.is_public = 1
    ''', [card_id])
    
    # Get public wants
    wants = query_db('''
        SELECT user_cards.*, users.username
        FROM user_cards
        JOIN users ON user_cards.user_id = users.id
        WHERE user_cards.card_id = ? AND user_cards.list_type = 'want' AND user_cards.is_public = 1
    ''', [card_id])
    
    template = BASE_TEMPLATE + """
    {% block content %}
    <div class="container mx-auto px-4 py-8">
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <!-- Card Image -->
            <div class="bg-white p-6 rounded-lg shadow">
                {% if card.image_url %}
                <img src="{{ card.image_url }}" alt="{{ card.name }}" class="w-full max-w-md mx-auto">
                {% else %}
                <div class="w-full aspect-[2.5/3.5] bg-gray-200 flex items-center justify-center">
                    <span class="text-gray-400">No Image Available</span>
                </div>
                {% endif %}
            </div>

            <!-- Card Info -->
            <div>
                <h2 class="text-4xl font-bold mb-2">{{ card.name }}</h2>
                <p class="text-xl text-gray-600 mb-4">{{ card.set_name }} #{{ card.card_number }}</p>
                {% if card.rarity %}
                <p class="text-gray-600 mb-2"><strong>Rarity:</strong> {{ card.rarity }}</p>
                {% endif %}
                
                <!-- Market Stats -->
                <div class="bg-blue-50 p-6 rounded-lg mb-6">
                    <h3 class="text-xl font-bold mb-4">Market Intelligence</h3>
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <div class="text-sm text-gray-600">Active Listings</div>
                            <div class="text-2xl font-bold">{{ listings|length }}</div>
                        </div>
                        <div>
                            <div class="text-sm text-gray-600">Want This</div>
                            <div class="text-2xl font-bold">{{ wants|length }}</div>
                        </div>
                        {% if listings %}
                        <div>
                            <div class="text-sm text-gray-600">Floor Price</div>
                            <div class="text-2xl font-bold text-green-600">${{ "%.2f"|format(listings[0].price) }}</div>
                        </div>
                        <div>
                            <div class="text-sm text-gray-600">Avg Price</div>
                            <div class="text-2xl font-bold">${{ "%.2f"|format((listings|sum(attribute='price')) / (listings|length)) }}</div>
                        </div>
                        {% endif %}
                    </div>
                </div>

                <!-- Active Listings -->
                {% if listings %}
                <h3 class="text-2xl font-bold mb-4">Active Listings ({{ listings|length }})</h3>
                <div class="space-y-3 mb-6">
                    {% for listing in listings %}
                    <div class="bg-white p-4 rounded-lg shadow border-l-4 border-green-500">
                        <div class="flex justify-between items-start">
                            <div>
                                <p class="font-bold text-lg">${{ "%.2f"|format(listing.price) }}</p>
                                <p class="text-sm text-gray-600">{{ listing.condition or 'Not specified' }} • Qty: {{ listing.quantity }}</p>
                                <p class="text-sm text-gray-500">Seller: <a href="/binders/{{ listing.username }}" class="text-blue-600 hover:underline">{{ listing.username }}</a></p>
                                {% if listing.location_city %}
                                <p class="text-sm text-gray-500">📍 {{ listing.location_city }}, {{ listing.location_region }}</p>
                                {% endif %}
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                {% else %}
                <p class="text-gray-600 mb-6">No active listings for this card.</p>
                {% endif %}

                <!-- Want List -->
                {% if wants %}
                <h3 class="text-xl font-bold mb-3">{{ wants|length }} collectors want this</h3>
                <div class="flex flex-wrap gap-2">
                    {% for want in wants %}
                    <a href="/binders/{{ want.username }}" class="text-blue-600 hover:underline">{{ want.username }}</a>
                    {% endfor %}
                </div>
                {% endif %}
            </div>
        </div>
    </div>
    {% endblock %}
    """
    
    return render_template_string(template, card=card, listings=listings, haves=haves, wants=wants)

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
    
    template = BASE_TEMPLATE + """
    {% block content %}
    <div class="container mx-auto px-4 py-8">
        <h2 class="text-3xl font-bold mb-6">All Active Listings ({{ listings|length }})</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {% for listing in listings %}
            <div class="bg-white rounded-lg shadow-lg overflow-hidden hover:shadow-xl transition-shadow">
                {% if listing.image_url %}
                <a href="/cards/{{ listing.card_id }}">
                    <img src="{{ listing.image_url }}" alt="{{ listing.card_name }}" class="w-full h-64 object-contain bg-gray-100 p-4 hover:bg-gray-50">
                </a>
                {% else %}
                <div class="w-full h-64 bg-gray-200 flex items-center justify-center">
                    <span class="text-gray-400">No Image</span>
                </div>
                {% endif %}
                <div class="p-4">
                    <h4 class="font-bold text-lg">{{ listing.card_name }}</h4>
                    <p class="text-sm text-gray-600">{{ listing.set_name }}</p>
                    <div class="flex justify-between items-center mt-4">
                        <span class="text-2xl font-bold text-green-600">${{ "%.2f"|format(listing.price) }}</span>
                        <span class="text-sm text-gray-500">{{ listing.username }}</span>
                    </div>
                    <a href="/cards/{{ listing.card_id }}" class="block w-full mt-4 bg-blue-600 text-white py-2 rounded hover:bg-blue-700 text-center">
                        View Card
                    </a>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
    {% endblock %}
    """
    
    return render_template_string(template, listings=all_listings)

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
    
    template = BASE_TEMPLATE + """
    {% block content %}
    <div class="container mx-auto px-4 py-8">
        <h2 class="text-3xl font-bold mb-6">Events & Card Shows</h2>
        <div class="space-y-6">
            {% for event in events %}
            <div class="bg-white p-6 rounded-lg shadow-lg hover:shadow-xl transition-shadow">
                <div class="flex justify-between items-start">
                    <div class="flex-1">
                        <h3 class="text-2xl font-bold mb-2">{{ event.name }}</h3>
                        <p class="text-gray-600 mb-2">📍 {{ event.location_venue }}{% if event.location_city %}, {{ event.location_city }}, {{ event.location_region }}{% endif %}</p>
                        <p class="text-gray-600 mb-2">📅 {{ event.start_datetime[:10] }}{% if event.end_datetime %} - {{ event.end_datetime[:10] }}{% endif %}</p>
                        {% if event.website_url %}
                        <p class="text-sm mb-2"><a href="{{ event.website_url }}" target="_blank" class="text-blue-600 hover:underline">🔗 Event Website</a></p>
                        {% endif %}
                        {% if event.description %}
                        <p class="text-gray-700 mt-4">{{ event.description }}</p>
                        {% endif %}
                        <div class="flex gap-6 mt-4 text-sm">
                            <span class="font-semibold">👥 {{ event.attendee_count }} attending</span>
                            <span class="font-semibold">🎴 {{ event.cards_count }} cards listed</span>
                        </div>
                    </div>
                    <a href="/events/{{ event.id }}" class="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700">
                        View Details
                    </a>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
    {% endblock %}
    """
    
    return render_template_string(template, events=all_events)

@app.route('/events/<int:event_id>')
def event_detail(event_id):
    """Detailed event view with attendees and cards"""
    event = query_db('SELECT * FROM events WHERE id = ?', [event_id], one=True)
    
    if not event:
        flash('Event not found', 'error')
        return redirect(url_for('events'))
    
    attendees = query_db('''
        SELECT users.username, users.location_city, event_attendance.role, event_attendance.status
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
    
    template = BASE_TEMPLATE + """
    {% block content %}
    <div class="container mx-auto px-4 py-8">
        <div class="bg-white p-8 rounded-lg shadow-lg mb-8">
            <h2 class="text-4xl font-bold mb-4">{{ event.name }}</h2>
            <p class="text-xl text-gray-600 mb-4">📍 {{ event.location_venue }}{% if event.location_city %}, {{ event.location_city }}, {{ event.location_region }}{% endif %}</p>
            <p class="text-gray-600 mb-4">📅 {{ event.start_datetime }}{% if event.end_datetime %} - {{ event.end_datetime }}{% endif %}</p>
            {% if event.website_url %}
            <p class="mb-4"><a href="{{ event.website_url }}" target="_blank" class="text-blue-600 hover:underline">🔗 Event Website</a></p>
            {% endif %}
            {% if event.description %}
            <p class="text-gray-700">{{ event.description }}</p>
            {% endif %}
        </div>

        <!-- Attendees -->
        {% if attendees %}
        <div class="bg-white p-6 rounded-lg shadow-lg mb-8">
            <h3 class="text-2xl font-bold mb-4">Attendees ({{ attendees|length }})</h3>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {% for attendee in attendees %}
                <div class="border p-4 rounded">
                    <p class="font-bold">{{ attendee.username }}</p>
                    {% if attendee.role %}
                    <p class="text-sm text-gray-600">{{ attendee.role|title }}</p>
                    {% endif %}
                    {% if attendee.location_city %}
                    <p class="text-sm text-gray-500">{{ attendee.location_city }}</p>
                    {% endif %}
                    <span class="text-xs bg-green-100 text-green-800 px-2 py-1 rounded mt-2 inline-block">{{ attendee.status }}</span>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}

        <!-- Cards at Event -->
        {% if cards_at_event %}
        <div class="bg-white p-6 rounded-lg shadow-lg">
            <h3 class="text-2xl font-bold mb-4">Cards at This Event ({{ cards_at_event|length }})</h3>
            <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                {% for card in cards_at_event %}
                <div class="bg-white rounded shadow overflow-hidden">
                    {% if card.image_url %}
                    <img src="{{ card.image_url }}" alt="{{ card.name }}" class="w-full aspect-[2.5/3.5] object-contain bg-gray-100">
                    {% else %}
                    <div class="w-full aspect-[2.5/3.5] bg-gray-200"></div>
                    {% endif %}
                    <div class="p-2">
                        <p class="font-bold text-sm truncate">{{ card.name }}</p>
                        <p class="text-xs text-gray-600">by {{ card.username }}</p>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}
    </div>
    {% endblock %}
    """
    
    return render_template_string(template, event=event, attendees=attendees, cards_at_event=cards_at_event)

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
        LEFT JOIN listings ON users.id = listings.user_id AND listings.status = 'active'
        GROUP BY users.id
        ORDER BY have_count DESC
    ''')
    
    template = BASE_TEMPLATE + """
    {% block content %}
    <div class="container mx-auto px-4 py-8">
        <h2 class="text-3xl font-bold mb-6">Public Binders</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {% for user in users %}
            <div class="bg-white p-6 rounded-lg shadow-lg hover:shadow-xl transition-shadow">
                <div class="text-center mb-4">
                    <div class="w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full mx-auto mb-3 flex items-center justify-center text-white text-3xl font-bold">
                        {{ user.username[:2].upper() }}
                    </div>
                    <h3 class="font-bold text-xl">{{ user.username }}</h3>
                    {% if user.location_city %}
                    <p class="text-sm text-gray-600">{{ user.location_city }}, {{ user.location_region }}</p>
                    {% endif %}
                </div>
                {% if user.bio %}
                <p class="text-sm text-gray-700 mb-4">{{ user.bio }}</p>
                {% endif %}
                <div class="grid grid-cols-3 gap-2 text-center mb-4">
                    <div>
                        <div class="text-sm text-gray-600">Haves</div>
                        <div class="text-xl font-bold">{{ user.have_count }}</div>
                    </div>
                    <div>
                        <div class="text-sm text-gray-600">Wants</div>
                        <div class="text-xl font-bold">{{ user.want_count }}</div>
                    </div>
                    <div>
                        <div class="text-sm text-gray-600">Listings</div>
                        <div class="text-xl font-bold">{{ user.listing_count }}</div>
                    </div>
                </div>
                <a href="/binders/{{ user.username }}" class="block w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700 text-center">
                    View Binder
                </a>
            </div>
            {% endfor %}
        </div>
    </div>
    {% endblock %}
    """
    
    return render_template_string(template, users=users_list)

@app.route('/binders/<username>')
def user_binder(username):
    """View a specific user's public binder"""
    user = query_db('SELECT * FROM users WHERE username = ?', [username], one=True)
    
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('binders'))
    
    haves = query_db('''
        SELECT user_cards.*, cards.name, cards.image_url, sets.name as set_name
        FROM user_cards
        JOIN cards ON user_cards.card_id = cards.id
        JOIN sets ON cards.set_id = sets.id
        WHERE user_cards.user_id = ? AND user_cards.list_type = 'have' AND user_cards.is_public = 1
        ORDER BY cards.name
    ''', [user['id']])
    
    wants = query_db('''
        SELECT user_cards.*, cards.name, cards.image_url, sets.name as set_name
        FROM user_cards
        JOIN cards ON user_cards.card_id = cards.id
        JOIN sets ON cards.set_id = sets.id
        WHERE user_cards.user_id = ? AND user_cards.list_type = 'want' AND user_cards.is_public = 1
        ORDER BY cards.name
    ''', [user['id']])
    
    listings = query_db('''
        SELECT listings.*, cards.name, cards.image_url
        FROM listings
        JOIN cards ON listings.card_id = cards.id
        WHERE listings.user_id = ? AND listings.status = 'active'
    ''', [user['id']])
    
    template = BASE_TEMPLATE + """
    {% block content %}
    <div class="container mx-auto px-4 py-8">
        <div class="bg-white p-8 rounded-lg shadow-lg mb-8">
            <div class="flex items-center gap-6">
                <div class="w-24 h-24 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white text-4xl font-bold">
                    {{ user.username[:2].upper() }}
                </div>
                <div>
                    <h2 class="text-4xl font-bold">{{ user.username }}</h2>
                    {% if user.location_city %}
                    <p class="text-xl text-gray-600">{{ user.location_city }}, {{ user.location_region }}</p>
                    {% endif %}
                    {% if user.bio %}
                    <p class="text-gray-700 mt-2">{{ user.bio }}</p>
                    {% endif %}
                </div>
            </div>
        </div>

        <!-- Haves -->
        <section class="mb-12">
            <h3 class="text-2xl font-bold mb-4">Collection ({{ haves|length }})</h3>
            {% if haves %}
            <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                {% for card in haves %}
                <a href="/cards/{{ card.card_id }}" class="bg-white rounded-lg shadow overflow-hidden hover:shadow-lg transition-shadow">
                    <img src="{{ card.image_url }}" alt="{{ card.name }}" class="w-full aspect-[2.5/3.5] object-contain bg-gray-100">
                    <div class="p-2">
                        <p class="font-bold text-sm truncate">{{ card.name }}</p>
                        <p class="text-xs text-gray-600">{{ card.condition or 'N/A' }}</p>
                    </div>
                </a>
                {% endfor %}
            </div>
            {% else %}
            <p class="text-gray-600">No public collection.</p>
            {% endif %}
        </section>

        <!-- Wants -->
        <section class="mb-12">
            <h3 class="text-2xl font-bold mb-4">Want List ({{ wants|length }})</h3>
            {% if wants %}
            <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                {% for card in wants %}
                <a href="/cards/{{ card.card_id }}" class="bg-white rounded-lg shadow overflow-hidden border-2 border-yellow-400 hover:shadow-lg transition-shadow">
                    <img src="{{ card.image_url }}" alt="{{ card.name }}" class="w-full aspect-[2.5/3.5] object-contain bg-gray-100">
                    <div class="p-2">
                        <p class="font-bold text-sm truncate">{{ card.name }}</p>
                        {% if card.target_price %}
                        <p class="text-xs text-green-600">Target: ${{ "%.2f"|format(card.target_price) }}</p>
                        {% endif %}
                    </div>
                </a>
                {% endfor %}
            </div>
            {% else %}
            <p class="text-gray-600">No public want list.</p>
            {% endif %}
        </section>

        <!-- Active Listings -->
        {% if listings %}
        <section>
            <h3 class="text-2xl font-bold mb-4">Active Listings ({{ listings|length }})</h3>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                {% for listing in listings %}
                <div class="bg-white rounded-lg shadow p-4">
                    <img src="{{ listing.image_url }}" alt="{{ listing.name }}" class="w-full aspect-[2.5/3.5] object-contain bg-gray-100 rounded mb-2">
                    <p class="font-bold">{{ listing.name }}</p>
                    <p class="text-2xl font-bold text-green-600">${{ "%.2f"|format(listing.price) }}</p>
                    <p class="text-sm text-gray-600">{{ listing.condition }}</p>
                </div>
                {% endfor %}
            </div>
        </section>
        {% endif %}
    </div>
    {% endblock %}
    """
    
    return render_template_string(template, user=user, haves=haves, wants=wants, listings=listings)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = query_db('SELECT * FROM users WHERE username = ?', [username], one=True)
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
    
    template = BASE_TEMPLATE + """
    {% block content %}
    <div class="container mx-auto px-4 py-8 max-w-md">
        <div class="bg-white p-8 rounded-lg shadow-lg">
            <h2 class="text-3xl font-bold mb-6 text-center">Login</h2>
            <form method="POST">
                <div class="mb-4">
                    <label class="block text-gray-700 mb-2">Username</label>
                    <input type="text" name="username" required class="w-full px-4 py-2 border rounded">
                </div>
                <div class="mb-6">
                    <label class="block text-gray-700 mb-2">Password</label>
                    <input type="password" name="password" required class="w-full px-4 py-2 border rounded">
                </div>
                <button type="submit" class="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700">
                    Login
                </button>
            </form>
            <p class="text-center mt-4 text-sm">
                Don't have an account? <a href="/register" class="text-blue-600 hover:underline">Register</a>
            </p>
        </div>
    </div>
    {% endblock %}
    """
    
    return render_template_string(template)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        location_city = request.form.get('location_city')
        location_region = request.form.get('location_region')
        
        existing = query_db('SELECT id FROM users WHERE username = ? OR email = ?', [username, email], one=True)
        if existing:
            flash('Username or email already exists', 'error')
        else:
            now = datetime.now().isoformat()
            execute_db('''
                INSERT INTO users (username, email, password_hash, location_city, location_region, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', [username, email, generate_password_hash(password), location_city, location_region, now, now])
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
    
    template = BASE_TEMPLATE + """
    {% block content %}
    <div class="container mx-auto px-4 py-8 max-w-md">
        <div class="bg-white p-8 rounded-lg shadow-lg">
            <h2 class="text-3xl font-bold mb-6 text-center">Register</h2>
            <form method="POST">
                <div class="mb-4">
                    <label class="block text-gray-700 mb-2">Username *</label>
                    <input type="text" name="username" required class="w-full px-4 py-2 border rounded">
                </div>
                <div class="mb-4">
                    <label class="block text-gray-700 mb-2">Email *</label>
                    <input type="email" name="email" required class="w-full px-4 py-2 border rounded">
                </div>
                <div class="mb-4">
                    <label class="block text-gray-700 mb-2">Password *</label>
                    <input type="password" name="password" required class="w-full px-4 py-2 border rounded">
                </div>
                <div class="mb-4">
                    <label class="block text-gray-700 mb-2">City</label>
                    <input type="text" name="location_city" class="w-full px-4 py-2 border rounded">
                </div>
                <div class="mb-6">
                    <label class="block text-gray-700 mb-2">State/Region</label>
                    <input type="text" name="location_region" class="w-full px-4 py-2 border rounded">
                </div>
                <button type="submit" class="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700">
                    Register
                </button>
            </form>
            <p class="text-center mt-4 text-sm">
                Already have an account? <a href="/login" class="text-blue-600 hover:underline">Login</a>
            </p>
        </div>
    </div>
    {% endblock %}
    """
    
    return render_template_string(template)

@app.route('/logout')
def logout():
    """User logout"""
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

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
    
    template = BASE_TEMPLATE + """
    {% block content %}
    <div class="container mx-auto px-4 py-8">
        <h2 class="text-3xl font-bold mb-6">My Binder</h2>
        
        <!-- Haves -->
        <section class="mb-12">
            <h3 class="text-2xl font-bold mb-4">My Collection ({{ haves|length }})</h3>
            {% if haves %}
            <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                {% for card in haves %}
                <div class="bg-white rounded-lg shadow overflow-hidden">
                    <img src="{{ card.image_url }}" alt="{{ card.name }}" class="w-full aspect-[2.5/3.5] object-contain bg-gray-100">
                    <div class="p-2">
                        <p class="font-bold text-sm truncate">{{ card.name }}</p>
                        <p class="text-xs text-gray-600">{{ card.condition or 'N/A' }}</p>
                        {% if card.is_public %}
                        <span class="text-xs text-green-600">✓ Public</span>
                        {% else %}
                        <span class="text-xs text-gray-400">Private</span>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <p class="text-gray-600">No cards in your collection yet.</p>
            {% endif %}
        </section>
        
        <!-- Wants -->
        <section>
            <h3 class="text-2xl font-bold mb-4">My Wants ({{ wants|length }})</h3>
            {% if wants %}
            <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                {% for card in wants %}
                <div class="bg-white rounded-lg shadow overflow-hidden border-2 border-yellow-400">
                    <img src="{{ card.image_url }}" alt="{{ card.name }}" class="w-full aspect-[2.5/3.5] object-contain bg-gray-100">
                    <div class="p-2">
                        <p class="font-bold text-sm truncate">{{ card.name }}</p>
                        {% if card.target_price %}
                        <p class="text-xs text-green-600">Target: ${{ "%.2f"|format(card.target_price) }}</p>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <p class="text-gray-600">No cards in your want list yet.</p>
            {% endif %}
        </section>
    </div>
    {% endblock %}
    """
    
    return render_template_string(template, haves=haves, wants=wants)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)