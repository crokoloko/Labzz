import sqlite3
import random
import time
from datetime import datetime

# ==========================================
# 1. DATABASE & PERSISTENZA DEL GIOCO
# ==========================================
class GameDatabase:
    def __init__(self, db_name="game_empire.db"):
        self.db_name = db_name
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Tabella Prodotti
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS prodotti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL,
                prezzo_mercato REAL DEFAULT 0.0,
                scorta_minima REAL DEFAULT 10.0
            )""")
            # Tabella Lotti (Magazzino)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS lotti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prodotto_id INTEGER,
                codice_lotto TEXT,
                qta_iniziale REAL,
                qta_attuale REAL,
                costo_unitario REAL,
                FOREIGN KEY (prodotto_id) REFERENCES prodotti (id)
            )""")
            # Tabella Storico Movimenti
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS movimenti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prodotto_id INTEGER,
                tipo TEXT,
                quantita REAL,
                ricavo REAL,
                costo REAL,
                margine REAL,
                cliente TEXT,
                pagamento TEXT,
                data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")

# ==========================================
# 2. ENTITÀ DI GIOCO (PLAYER, CLIENTE, BOT)
# ==========================================
class Player:
    def __init__(self, name="CEO Alex"):
        self.name = name
        self.cash = 1000.0        # Euro iniziali
        self.energy = 100         # Energia (0 - 100)
        self.reputation = 50      # Reputazione (0 - 100)
        self.day = 1

    def rest(self):
        self.energy = min(100, self.energy + 40)
        print(f"\n💤 {self.name} ha riposato. Energia ripristinata a {self.energy}%.")

class CustomerAI:
    """Generatore di Clienti PNG con comportamenti dinamici"""
    def __init__(self):
        names = ["Marco", "Elena", "Giuseppe", "Sara", "Luca", "Chiara", "Anonimo"]
        self.name = random.choice(names)
        self.budget = random.uniform(20.0, 150.0)
        self.max_price_per_g = random.uniform(2.5, 5.0)
        self.wants_credit = random.random() < 0.25 # 25% di probabilità di chiedere credito

class SalesEngine:
    """Motore di automazione delle vendite"""
    def __init__(self, db):
        self.db = db

    def process_turn(self, player):
        print(f"\n--- 🏪 APERTURA NEGOZIO - GIORNO {player.day} ---")
        num_customers = random.randint(3, 7)
        sales_count = 0
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # Recupera prodotti con disponibilità > 0
            cursor.execute("""
                SELECT p.id, p.nome, p.prezzo_mercato, SUM(l.qta_attuale) 
                FROM prodotti p JOIN lotti l ON p.id = l.prodotto_id 
                WHERE l.qta_attuale > 0 GROUP BY p.id
            """)
            available_products = cursor.fetchall()

            if not available_products:
                print("⚠️ Magazzino vuoto! Impossibile effettuare vendite oggi.")
                return

            for _ in range(num_customers):
                customer = CustomerAI()
                prod_id, prod_nome, prezzo_u, qta_disp = random.choice(available_products)

                # Decisione d'acquisto del PNG
                if prezzo_u <= customer.max_price_per_g and qta_disp > 0:
                    qta_desiderata = min(qta_disp, round(customer.budget / prezzo_u, 1))
                    if qta_desiderata <= 0:
                        continue

                    # Scarico FIFO dal magazzino
                    cursor.execute("SELECT id, qta_attuale, costo_unitario FROM lotti WHERE prodotto_id = ? AND qta_attuale > 0 ORDER BY id ASC", (prod_id,))
                    lotti = cursor.fetchall()
                    
                    qta_rimasta = qta_desiderata
                    costo_totale_transazione = 0.0

                    for l_id, l_qta, l_costo in lotti:
                        if qta_rimasta <= 0:
                            break
                        prelievo = min(l_qta, qta_rimasta)
                        cursor.execute("UPDATE lotti SET qta_attuale = qta_attuale - ? WHERE id = ?", (prelievo, l_id))
                        qta_rimasta -= prelievo
                        costo_totale_transazione += prelievo * l_costo

                    ricavo = qta_desiderata * prezzo_u
                    margine = ricavo - costo_totale_transazione
                    pagamento = "Dopo (Credito)" if customer.wants_credit else "Subito"

                    if pagamento == "Subito":
                        player.cash += ricavo

                    # Registrazione Movimento nel DB
                    cursor.execute("""
                        INSERT INTO movimenti (prodotto_id, tipo, quantita, ricavo, costo, margine, cliente, pagamento)
                        VALUES (?, 'VENDITA', ?, ?, ?, ?, ?, ?)
                    """, (prod_id, qta_desiderata, ricavo, costo_totale_transazione, margine, customer.name, pagamento))

                    sales_count += 1
                    status_pag = "💳 (A CREDITO)" if pagamento == "Dopo (Credito)" else "💰 (SUBITO)"
                    print(f"✅ Venduti {qta_desiderata}g di {prod_nome} a {customer.name} per €{ricavo:.2f} {status_pag}")

        print(f"📊 Fine turno: Effettuate {sales_count} vendite su {num_customers} clienti entrati.")

# ==========================================
# 3. GAME LOOP PRINCIPALE
# ==========================================
def main():
    db = GameDatabase()
    player = Player()
    engine = SalesEngine(db)

    # Popola DB con dati iniziali se vuoto
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM prodotti")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO prodotti (nome, prezzo_mercato, scorta_minima) VALUES ('Varietà Premium', 3.5, 20.0)")
            p_id = cursor.lastrowid
            cursor.execute("INSERT INTO lotti (prodotto_id, codice_lotto, qta_iniziale, qta_attuale, costo_unitario) VALUES (?, 'L100', 200.0, 200.0, 1.2)", (p_id,))

    # Loop di Gioco Operativo
    while True:
        print("\n" + "="*40)
        print(f"🏢 EMPIRE TYCOON | Giorno {player.day} | Cassa: €{player.cash:.2f} | Energia: {player.energy}%")
        print("="*40)
        print("1. 🏪 Avvia Turno di Vendita Automatica")
        print("2. 🚚 Acquista Rifornimento (Nuovo Lotto)")
        print("3. 🧪 Uso Personale (XME) -> Recupera Energia")
        print("4. 💤 Riposa e Passa al Giorno Successivo")
        print("5. 🚪 Esci dal Gioco")

        scelta = input("\nSeleziona un'azione: ")

        if scelta == "1":
            if player.energy < 15:
                print("⚠️ Sei troppo stanco per aprire il negozio! Riposa prima.")
            else:
                player.energy -= 15
                engine.process_turn(player)
        elif scelta == "2":
            costo_lotto = 150.0
            if player.cash >= costo_lotto:
                player.cash -= costo_lotto
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO lotti (prodotto_id, codice_lotto, qta_iniziale, qta_attuale, costo_unitario) VALUES (1, 'BATCH_NEW', 100.0, 100.0, 1.5)")
                print("✅ Rifornimento effettuato! Aggiunti 100g in magazzino.")
            else:
                print("❌ Fondi insufficienti per ordinare un nuovo lotto.")
        elif scelta == "3":
            # Meccanica XME convertita in gameplay perk
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, qta_attuale FROM lotti WHERE qta_attuale >= 10 LIMIT 1")
                lotto = cursor.fetchone()
                if lotto:
                    cursor.execute("UPDATE lotti SET qta_attuale = qta_attuale - 10 WHERE id = ?", (lotto[0],))
                    player.energy = min(100, player.energy + 25)
                    print("🧪 Operazione XME completata. Energia aumentata di +25%!")
                else:
                    print("❌ Scorte insufficienti in magazzino per eseguire XME.")
        elif scelta == "4":
            player.rest()
            player.day += 1
        elif scelta == "5":
            print("Salvataggio ed uscita dal gioco...")
            break

if __name__ == "__main__":
    main()