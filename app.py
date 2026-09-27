import sqlite3
import base64
import os
import random
from datetime import datetime, date, timedelta
import pandas as pd
import streamlit as st
import altair as alt

# ==========================================
# CONFIGURAZIONE PAGINA STREAMLIT
# ==========================================
st.set_page_config(
    page_title="LaBzz - Praga Underground Tycoon",
    page_icon="📦",
    layout="wide"
)

# ==========================================
# HELPER & FUNZIONI DATABASE & CALENDARIO
# ==========================================
DB_NAME = "magazzino.db"

def get_connection():
    return sqlite3.connect(DB_NAME, timeout=10)

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS prodotti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            unita_misura TEXT DEFAULT 'g',
            valore_mercato_unitario REAL DEFAULT 0,
            scorta_minima_g REAL DEFAULT 0
        )""")
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS lotti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prodotto_id INTEGER NOT NULL,
            codice_lotto TEXT NOT NULL,
            quantita_iniziale REAL NOT NULL,
            quantita_attuale REAL NOT NULL,
            costo_acquisto_unitario REAL NOT NULL,
            data_acquisto DATE,
            data_carico DATE NOT NULL,
            data_completamento DATE,
            FOREIGN KEY (prodotto_id) REFERENCES prodotti (id) ON DELETE CASCADE
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS clienti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pusher (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            quota_trattenuta REAL NOT NULL,
            efficienza REAL NOT NULL,
            assunto INTEGER DEFAULT 0
        )""")
        
        try:
            cursor.execute("ALTER TABLE pusher ADD COLUMN quota_trattenuta REAL DEFAULT 0.25;")
        except sqlite3.OperationalError:
            pass

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prodotto_id INTEGER NOT NULL,
            lotto_id INTEGER,
            tipo TEXT NOT NULL,
            quantita REAL NOT NULL,
            prezzo_unitario REAL DEFAULT 0,
            ricavo_totale REAL DEFAULT 0,
            costo_totale REAL DEFAULT 0,
            margine REAL DEFAULT 0,
            note TEXT,
            cliente TEXT DEFAULT 'Anonimo',
            pagamento TEXT DEFAULT 'Subito',
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prodotto_id) REFERENCES prodotti (id) ON DELETE CASCADE,
            FOREIGN KEY (lotto_id) REFERENCES lotti (id) ON DELETE SET NULL
        )""")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS impostazioni (
            chiave TEXT PRIMARY KEY,
            valore REAL NOT NULL
        )""")
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('soglia_esaurimento', 10.0)")
        cursor.execute("INSERT OR IGNORE INTO impostazioni (chiave, valore) VALUES ('sospetto_polizia', 10.0)")

init_db()

FASCE_ORARIE = [
    "🌅 1. Mattina (08:00 - 11:30)", 
    "☀️ 2. Mezzogiorno (11:30 - 15:00)", 
    "🌇 3. Pomeriggio (15:00 - 18:30)", 
    "🌙 4. Sera (18:30 - 22:00)", 
    "🌌 5. Notte (22:00 - 02:00)"
]

LISTA_NOMI_PRAGA = [
    "Jan", "Petra", "Maxim", "Klara", "Tomas", "Lenka", "Wanja", 
    "Milan", "Zuzana", "Marek", "Sonja", "Ondra", "Katka", "Pavel", 
    "Hana", "Lukas", "Eliška", "Jakub", "Nikola", "David", "Veronika",
    "Martin", "Štěpán", "Markéta", "Filip", "Dominik", "Magda", "Sven",
    "Dmitri", "Natasha", "Alex", "Borislav", "Evelin", "Goran", "Ivana"
]

PUSHER_DISPONIBILI = [
    {"nome": "Vojta 'Il Veloce'", "quota_trattenuta": 0.25, "efficienza": 0.8},
    {"nome": "Kamil 'Ghost'", "quota_trattenuta": 0.35, "efficienza": 1.3},
    {"nome": "Anetka 'Bassi'", "quota_trattenuta": 0.40, "efficienza": 0.5}
]

def inizializza_pusher_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        for p in PUSHER_DISPONIBILI:
            cursor.execute("INSERT OR IGNORE INTO pusher (nome, quota_trattenuta, efficienza, assunto) VALUES (?, ?, ?, 0)", (p['nome'], p['quota_trattenuta'], p['efficienza']))
            cursor.execute("UPDATE pusher SET quota_trattenuta = ?, efficienza = ? WHERE nome = ?", (p['quota_trattenuta'], p['efficienza'], p['nome']))
inizializza_pusher_db()

def get_data_corrente_gioco():
    data_base = date(2026, 9, 27)
    giorni_trascorsi = st.session_state.giorni_trascorsi_offset
    return data_base + timedelta(days=giorni_trascorsi)

def e_festivo_o_weekend(data_rif):
    if data_rif.weekday() >= 5:
        return True, "Weekend / Rave in corso 🎉"
    return False, "Giorno Lavorativo 💼"

def get_video_base64(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode('utf-8')
    return None

def get_soglia_esaurimento():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT valore FROM impostazioni WHERE chiave = 'soglia_esaurimento'")
        row = cursor.fetchone()
        return float(row[0]) if row else 10.0

def get_sospetto():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT valore FROM impostazioni WHERE chiave = 'sospetto_polizia'")
        row = cursor.fetchone()
        return float(row[0]) if row else 10.0

def set_sospetto(valore):
    v_clamped = max(0.0, min(100.0, valore))
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO impostazioni (chiave, valore) VALUES ('sospetto_polizia', ?)", (v_clamped,))

def get_prodotti_disponibili_df():
    query = """
        SELECT DISTINCT p.id, p.nome, p.valore_mercato_unitario
        FROM prodotti p
        JOIN lotti l ON p.id = l.prodotto_id
        WHERE l.quantita_attuale > 0
        ORDER BY p.nome ASC
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)

def get_prodotti_tutti_df():
    with get_connection() as conn:
        return pd.read_sql_query("SELECT * FROM prodotti ORDER BY nome ASC", conn)

def get_lotti_attivi_df():
    query = """
        SELECT l.id, p.nome AS prodotto, l.codice_lotto, l.quantita_iniziale, l.quantita_attuale, 
               'g' AS unita_misura, l.costo_acquisto_unitario, l.data_acquisto, l.data_carico
        FROM lotti l
        JOIN prodotti p ON l.prodotto_id = p.id
        WHERE l.quantita_attuale > 0
        ORDER BY l.data_carico ASC, l.id ASC
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)

def get_report_lotti_integrato_df(soglia_esaurimento_g=10.0):
    query = """
        SELECT 
            l.id AS lotto_id,
            p.nome AS prodotto,
            l.codice_lotto,
            l.quantita_iniziale,
            l.quantita_attuale,
            'g' AS unita_misura,
            l.costo_acquisto_unitario,
            (l.quantita_iniziale * l.costo_acquisto_unitario) AS costo_totale_lotto,
            COALESCE(SUM(CASE WHEN m.tipo = 'VENDITA' THEN m.quantita ELSE 0 END), 0) AS qta_venduta_lotto,
            COALESCE(SUM(CASE WHEN m.tipo = 'VENDITA' THEN m.ricavo_totale ELSE 0 END), 0) AS incasso_totale_lotto,
            COALESCE(SUM(CASE WHEN m.tipo = 'VENDITA' THEN m.margine ELSE 0 END), 0) -
            COALESCE(SUM(CASE WHEN m.tipo = 'XME' THEN m.costo_totale ELSE 0 END), 0) AS guadagno_netto_lotto,
            l.data_acquisto,
            l.data_carico,
            l.data_completamento
        FROM lotti l
        JOIN prodotti p ON l.prodotto_id = p.id
        LEFT JOIN movimenti m ON l.id = m.lotto_id
        GROUP BY l.id
        ORDER BY l.data_carico DESC, l.id DESC
    """
    with get_connection() as conn:
        df = pd.read_sql_query(query, conn)

    if not df.empty:
        def calcola_stato(row):
            qta = float(row['quantita_attuale'])
            if qta == 0:
                dt_comp = row['data_completamento']
                return f"✅ Esaurito ({dt_comp})" if dt_comp else "✅ Esaurito"
            elif qta <= soglia_esaurimento_g:
                return f"⚠️ In Esaurimento ({qta:.1f} g rimasti)"
            else:
                return "🔵 Attivo"
        df['stato_lotto'] = df.apply(calcola_stato, axis=1)
    return df

def get_movimenti_dettagliati_df():
    query = """
        SELECT 
            m.id, 
            m.data, 
            p.nome AS prodotto, 
            COALESCE(l.codice_lotto, 'N/D') AS lotto,
            m.tipo, 
            m.quantita, 
            m.prezzo_unitario AS prezzo_g, 
            m.ricavo_totale AS incasso, 
            m.margine, 
            COALESCE(m.cliente, 'Anonimo') AS cliente,
            COALESCE(m.pagamento, 'Subito') AS stato_pagamento
        FROM movimenti m
        JOIN prodotti p ON m.prodotto_id = p.id
        LEFT JOIN lotti l ON m.lotto_id = l.id
        ORDER BY m.data DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)

def aggiungi_cliente_se_nuovo(nome):
    if nome and nome.strip() != "":
        nome_pulito = nome.strip().capitalize()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO clienti (nome) VALUES (?)", (nome_pulito,))

def calcola_grado_reputazione(rep):
    if rep < 30:
        return "🌱 Principiante di Žižkov"
    elif rep < 60:
        return "🥈 Player Rispettato a Praga"
    elif rep < 85:
        return "🥇 Boss Underground"
    else:
        return "👑 Re della Notte di Praga"

def calcola_stato_magazzino(solo_disponibili=False):
    with get_connection() as conn:
        prodotti_df = pd.read_sql_query("SELECT * FROM prodotti", conn)
        lotti_df = pd.read_sql_query("SELECT * FROM lotti WHERE quantita_attuale > 0", conn)
        movimenti_df = pd.read_sql_query("SELECT * FROM movimenti", conn)

    risultati = []
    for _, prod in prodotti_df.iterrows():
        p_id = prod['id']
        lotti_prod = lotti_df[lotti_df['prodotto_id'] == p_id]
        qta_totale = float(lotti_prod['quantita_attuale'].sum())
        
        if solo_disponibili and qta_totale <= 0:
            continue

        valore_costo_totale = float((lotti_prod['quantita_attuale'] * lotti_prod['costo_acquisto_unitario']).sum())
        costo_medio = valore_costo_totale / qta_totale if qta_totale > 0 else 0.0
        valore_mercato_totale = qta_totale * prod['valore_mercato_unitario']
        
        vendite = movimenti_df[(movimenti_df['prodotto_id'] == p_id) & (movimenti_df['tipo'] == 'VENDITA')]
        qta_venduta = float(vendite['quantita'].sum())
        incasso_totale = float(vendite['ricavo_totale'].sum())
        margine_totale = float(vendite['margine'].sum())

        risultati.append({
            'prodotto_id': p_id,
            'prodotto': prod['nome'],
            'unita_misura': 'g',
            'qta_disponibile': qta_totale,
            'scorta_minima_g': float(prod['scorta_minima_g']),
            'costo_medio_ponderato': costo_medio,
            'valore_mercato_unitario': float(prod['valore_mercato_unitario']),
            'valore_totale_costo': valore_costo_totale,
            'valore_totale_mercato': valore_mercato_totale,
            'qta_venduta': qta_venduta,
            'incasso_totale': incasso_totale,
            'margine_totale': margine_totale
        })
    return pd.DataFrame(risultati)

def segna_debito_pagato(nome_cliente):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(ricavo_totale) FROM movimenti WHERE cliente = ? AND pagamento = 'Dopo (Credito)'", (nome_cliente,))
        tot_incassato = cursor.fetchone()[0] or 0.0
        cursor.execute("UPDATE movimenti SET pagamento = 'Subito' WHERE cliente = ? AND pagamento = 'Dopo (Credito)'", (nome_cliente,))
        st.session_state.soldi_cassa += tot_incassato

def spara_fuochi_d_artificio():
    js_code = """
    <script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"></script>
    <script>
        var count = 200;
        var defaults = { origin: { y: 0.7 } };
        function fire(particleRatio, opts) {
          confetti(Object.assign({}, defaults, opts, {
            particleCount: Math.floor(count * particleRatio)
          }));
        }
        fire(0.25, { spread: 26, startVelocity: 55 });
        fire(0.2, { spread: 60 });
        fire(0.35, { spread: 100, decay: 0.91, scalar: 0.8 });
    </script>
    """
    st.components.v1.html(js_code, height=0)

def trigger_effetto_notte():
    js_code = """
    <div id="night-overlay" style="
        position: fixed;
        top: 0; left: 0; width: 100vw; height: 100vh;
        background: linear-gradient(180deg, #020617 0%, #090d16 50%, #1e1b4b 100%);
        backdrop-filter: blur(0px);
        z-index: 99999;
        opacity: 0;
        pointer-events: none;
        transition: opacity 1.2s ease-in-out, backdrop-filter 1.2s ease-in-out;
        display: flex;
        justify-content: center;
        align-items: center;
        color: #fbbf24;
        font-family: 'Anton', sans-serif;
        font-size: 2.5rem;
        letter-spacing: 3px;
        text-shadow: 0 0 20px rgba(251, 191, 36, 0.6);
    ">🌙 PASSAGGIO DELLA NOTTE PRAGHESE... ALBA IN ARRIVO ☀️</div>
    <script>
        const overlay = document.getElementById('night-overlay');
        setTimeout(() => {
            overlay.style.opacity = '1';
            overlay.style.backdropFilter = 'blur(12px)';
        }, 50);
        setTimeout(() => {
            overlay.style.opacity = '0';
            overlay.style.backdropFilter = 'blur(0px)';
        }, 2200);
    </script>
    """
    st.components.v1.html(js_code, height=0)

# ==========================================
# GANGSTER E FORNITORI
# ==========================================
GANGSTER_FORNITORI = [
    {"nome": "Don Cornetto", "frase": "«Un'offerta da Praga che non puoi rifiutare...»"},
    {"nome": "Tony Pesto", "frase": "«O compri questo stock o stasera le cotolette le fai coi denti!»"},
    {"nome": "Al Cacio", "frase": "«Robina fresca fresca di contrabbando, scesa dal treno da Berlino.»"},
    {"nome": "Franky 'Cinque Dita'", "frase": "«Guarda che qualità, sfiorala soltanto e ti senti a Karlin!»"},
    {"nome": "Peppe 'u Scannatore", "frase": "«Vedi di fare in fretta prima che arrivi la polizia ceca...»"},
    {"nome": "Luigi 'O Calibro", "frase": "«Prezzo da amico, ma non farmi domande su dove l'ho preso nei club.»"}
]

def genera_offerta_fornitore_casuale():
    if st.session_state.fornitori_visti_oggi >= st.session_state.max_fornitori_oggi:
        st.info("Per oggi non ci sono altri contatti disponibili nei vicoli.")
        return

    st.session_state.fornitori_visti_oggi += 1
    gangster = random.choice(GANGSTER_FORNITORI)
    
    giorno_corrente = st.session_state.giorno
    moltiplicatore_giornaliero = 1.0 + min(2.5, (giorno_corrente - 1) * 0.18)
    
    rischio_sola = random.random() < (0.18 + min(0.30, giorno_corrente * 0.02))
    
    if rischio_sola:
        tipo_offerta = "⚠️ ATTENZIONE: Sospetta 'Sola' / Pacco!"
        p_nome = "Skunk"
        qta = float(random.choice([80, 100, 150, 200]) * moltiplicatore_giornaliero)
        costo_u = round(random.uniform(3.00, 4.20), 2)
        valore_mercato_suggerito = 7.0
        gangster_frase_sola = f"«{gangster['nome']} ti guarda con un ghigno strano...» " + gangster['frase']
    else:
        varieta_scelta = random.choices(
            ["Skunk", "Hash Dry", "Lemon Haze", "Frozen Hash"],
            weights=[40, 35, 18, 7],
            k=1
        )[0]
        
        if varieta_scelta == "Skunk":
            p_nome = "Skunk"
            qta = float(random.choice([60, 100, 150, 200]) * moltiplicatore_giornaliero)
            costo_u = round(random.uniform(2.50, 3.50), 2)
            valore_mercato_suggerito = 7.0
            tipo_offerta = "🌿 Skunk Economica"

        elif varieta_scelta == "Hash Dry":
            p_nome = "Hash Dry"
            qta = float(random.choice([40, 80, 120, 160]) * moltiplicatore_giornaliero)
            costo_u = round(random.uniform(4.00, 5.50), 2)
            valore_mercato_suggerito = 10.0
            tipo_offerta = "🧱 Hash Dry Commerciale"

        elif varieta_scelta == "Lemon Haze":
            p_nome = "Lemon Haze"
            qta = float(random.choice([30, 60, 100, 130]) * moltiplicatore_giornaliero)
            costo_u = round(random.uniform(6.50, 8.50), 2)
            valore_mercato_suggerito = 14.0
            tipo_offerta = "🍋 Lemon Haze (Ottima Qualità)"

        else:
            p_nome = "Frozen Hash"
            qta = float(random.choice([20, 35, 50, 70]) * moltiplicatore_giornaliero)
            costo_u = round(random.uniform(10.00, 13.50), 2)
            valore_mercato_suggerito = 22.0
            tipo_offerta = "❄️ Frozen Hash (💎 Stock Estremamente Raro)"

        gangster_frase_sola = gangster['frase']

    qta = round(qta, 1)
    costo_tot = round(qta * costo_u, 2)

    st.session_state.offerta_fornitore = {
        "fornitore_nome": gangster["nome"],
        "fornitore_frase": gangster_frase_sola,
        "prodotto_nome": p_nome,
        "quantita": qta,
        "costo_unitario": costo_u,
        "costo_totale": costo_tot,
        "valore_mercato_suggerito": valore_mercato_suggerito,
        "tipo": tipo_offerta,
        "is_sola": rischio_sola,
        "codice_lotto": f"PRG-{random.randint(100,999)}"
    }

def genera_cliente_in_negozio():
    prodotti_tutti = get_prodotti_tutti_df()
    if not prodotti_tutti.empty:
        prod = prodotti_tutti.sample(n=1).iloc[0]
        nome_c = random.choice(LISTA_NOMI_PRAGA)
        qta_req = float(random.choices([1, 2, 5, 10, 15, 20, 30], weights=[25, 30, 25, 12, 4, 3, 1], k=1)[0])
        val_ref = float(prod['valore_mercato_unitario'])
        budget_u = val_ref * random.uniform(0.85, 1.35)
        
        st.session_state.cliente_in_negozio = {
            "nome": nome_c,
            "prodotto_id": int(prod['id']),
            "prodotto_nome": prod['nome'],
            "quantita_richiesta": qta_req,
            "budget_max_g": round(budget_u, 2),
            "controfferta_attiva": False
        }
    else:
        st.session_state.cliente_in_negozio = None

def genera_evento_casuale_giorno():
    sosp = get_sospetto()
    if sosp >= 75.0 or random.random() < 0.35:
        evento_tipo = random.choice(["polizia", "vip", "tossici", "festival"])
        
        if evento_tipo == "polizia":
            st.session_state.evento_attivo = {
                "tipo": "polizia",
                "titolo": "🚨 BLITZ POLIZIA CECA / CONTROLLI METRO!",
                "testo": f"Il livello di sospetto è alto ({sosp:.1f}%). Pattuglie in borghese stazionano vicino al locale!"
            }
        elif evento_tipo == "vip":
            prodotti_disp = get_prodotti_disponibili_df()
            if not prodotti_disp.empty:
                prod_vip = prodotti_disp.sample(n=1).iloc[0]
                qta_vip = float(random.choice([5, 10, 15]))
                prezzo_vip = float(prod_vip['valore_mercato_unitario']) * 1.45
                st.session_state.evento_attivo = {
                    "tipo": "vip",
                    "titolo": "📱 NOTIFICA PROMOTORE CLUB VIP",
                    "testo": f"Un contatto underground ti scrive da Žižkov: «Mi servono urgentemente **{qta_vip}g di {prod_vip['nome']}** per un DJ set privato. Ti pago **€{prezzo_vip:.2f}/g**!»",
                    "prodotto_id": int(prod_vip['id']),
                    "prodotto_nome": prod_vip['nome'],
                    "quantita": qta_vip,
                    "prezzo_offerto": prezzo_vip
                }
            else:
                st.session_state.evento_attivo = None
        elif evento_tipo == "festival":
            st.session_state.evento_attivo = {
                "tipo": "festival",
                "titolo": "🎉 RAVER & TURISTI IN CITÀ!",
                "testo": "C'è un enorme festival di musica elettronica underground a Praga oggi! La richiesta di mercato schizza alle stelle (+20% sui prezzi di vendita per oggi)."
            }
        else:
            st.session_state.evento_attivo = {
                "tipo": "tossici",
                "titolo": "🧟 GRUPPO DI RIVALI LOCALI!",
                "testo": "Dei teppisti locali si aggirano fuori dal locale chiedendo il pizzo o minacciando scompiglio!"
            }
    else:
        st.session_state.evento_attivo = None

def esegui_transazione_vendita(cli_att, prezzo_per_g, tipo_pagamento):
    aggiungi_cliente_se_nuovo(cli_att['nome'])
    with get_connection() as conn:
        cursor = conn.cursor()
        lotti_df = pd.read_sql_query("SELECT id, quantita_attuale, costo_acquisto_unitario, codice_lotto FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0 ORDER BY data_carico ASC", conn, params=(cli_att['prodotto_id'],))
        
        qta_da_scaricare = cli_att['quantita_richiesta']
        totale_incasso = 0.0
        
        for _, lotto in lotti_df.iterrows():
            if qta_da_scaricare <= 0: break
            l_id = int(lotto['id'])
            qta_lotto_disp = float(lotto['quantita_attuale'])
            prelievo = min(qta_lotto_disp, qta_da_scaricare)
            nuova_qta = qta_lotto_disp - prelievo
            qta_da_scaricare -= prelievo
            
            ricavo_q = prelievo * prezzo_per_g
            costo_q = prelievo * float(lotto['costo_acquisto_unitario'])
            margine_q = ricavo_q - costo_q
            totale_incasso += ricavo_q
            
            if nuova_qta == 0:
                cursor.execute("UPDATE lotti SET quantita_attuale = 0, data_completamento = ? WHERE id = ?", (date.today(), l_id))
            else:
                cursor.execute("UPDATE lotti SET quantita_attuale = ? WHERE id = ?", (nuova_qta, l_id))
            
            cursor.execute("""
                INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, ricavo_totale, costo_totale, margine, cliente, pagamento, note)
                VALUES (?, ?, 'VENDITA', ?, ?, ?, ?, ?, ?, ?, ?)
            """, (cli_att['prodotto_id'], l_id, prelievo, prezzo_per_g, ricavo_q, costo_q, margine_q, cli_att['nome'], tipo_pagamento, f"Lotto {lotto['codice_lotto']}"))

    if tipo_pagamento == "Subito":
        st.session_state.soldi_cassa += totale_incasso

    st.session_state.energia = max(0, st.session_state.energia - 10)
    st.session_state.fedelta_clienti = min(100, st.session_state.fedelta_clienti + 3)
    st.session_state.reputazione = min(100, st.session_state.reputazione + 1)
    
    incremento_sospetto = cli_att['quantita_richiesta'] * 0.15
    if "Frozen" in cli_att['prodotto_nome']:
        incremento_sospetto *= 1.8
    set_sospetto(get_sospetto() + incremento_sospetto)

    aggiungi_log(f"✅ VENDITA: {cli_att['nome']} ha comprato {cli_att['quantita_richiesta']}g di '{cli_att['prodotto_nome']}' (+€{totale_incasso:.2f})")
    spara_fuochi_d_artificio()

# INITIAL STATE
if 'soldi_cassa' not in st.session_state:
    st.session_state.soldi_cassa = 200.0
if 'energia' not in st.session_state:
    st.session_state.energia = 100
if 'giorno' not in st.session_state:
    st.session_state.giorno = 1
if 'giorni_trascorsi_offset' not in st.session_state:
    st.session_state.giorni_trascorsi_offset = 0
if 'indice_fascia_oraria' not in st.session_state:
    st.session_state.indice_fascia_oraria = 0
if 'reputazione' not in st.session_state:
    st.session_state.reputazione = 15
if 'fedelta_clienti' not in st.session_state:
    st.session_state.fedelta_clienti = 10
if 'log_gioco' not in st.session_state:
    st.session_state.log_gioco = ["🎮 Benvenuto nel Praga Underground Tycoon! Capitale: €200."]
if 'offerta_fornitore' not in st.session_state:
    st.session_state.offerta_fornitore = None
if 'cliente_in_negozio' not in st.session_state:
    st.session_state.cliente_in_negozio = None
if 'fornitori_visti_oggi' not in st.session_state:
    st.session_state.fornitori_visti_oggi = 0
if 'max_fornitori_oggi' not in st.session_state:
    st.session_state.max_fornitori_oggi = random.choice([0, 1, 1, 2])
if 'evento_attivo' not in st.session_state:
    st.session_state.evento_attivo = None
if 'minigioco_trattativa' not in st.session_state:
    st.session_state.minigioco_trattativa = False
if 'ultimo_report_bot' not in st.session_state:
    st.session_state.ultimo_report_bot = None

if st.session_state.cliente_in_negozio is None:
    genera_cliente_in_negozio()

if st.session_state.giorno == 1 and st.session_state.offerta_fornitore is None and st.session_state.max_fornitori_oggi > 0:
    genera_offerta_fornitore_casuale()
    genera_evento_casuale_giorno()

def aggiungi_log(testo):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.log_gioco.insert(0, f"[{timestamp}] {testo}")

def reset_completo_nuova_partita():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM movimenti;")
        cursor.execute("DELETE FROM lotti;")
        cursor.execute("DELETE FROM prodotti;")
        cursor.execute("DELETE FROM clienti;")
        cursor.execute("UPDATE pusher SET assunto = 0;")
        
        cursor.execute("INSERT INTO prodotti (nome, valore_mercato_unitario, scorta_minima_g) VALUES ('Skunk', 7.0, 20.0);")
        p_id = cursor.lastrowid
        cursor.execute("INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico) VALUES (?, 'PRG-START', 50.0, 50.0, 2.50, ?, ?);", (p_id, date.today(), date.today()))
        l_id = cursor.lastrowid
        cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, costo_totale, cliente, note) VALUES (?, ?, 'CARICO', 50.0, 125.0, 'Fornitore Praga', 'Stock Iniziale')", (p_id, l_id))
    
    set_sospetto(10.0)
    st.session_state.soldi_cassa = 200.0
    st.session_state.giorno = 1
    st.session_state.giorni_trascorsi_offset = 0
    st.session_state.indice_fascia_oraria = 0
    st.session_state.energia = 100
    st.session_state.reputazione = 15
    st.session_state.fedelta_clienti = 10
    st.session_state.log_gioco = ["✨ Nuova Partita Iniziata! Praga ti aspetta. Budget: €200."]
    st.session_state.offerta_fornitore = None
    st.session_state.cliente_in_negozio = None
    st.session_state.fornitori_visti_oggi = 0
    st.session_state.max_fornitori_oggi = random.choice([0, 1, 2])
    st.session_state.evento_attivo = None
    st.session_state.minigioco_trattativa = False
    st.session_state.ultimo_report_bot = None
    if st.session_state.max_fornitori_oggi > 0:
        genera_offerta_fornitore_casuale()
    genera_cliente_in_negozio()
    genera_evento_casuale_giorno()

# ==========================================
# INIEZIONE CSS CUSTOM — STILE PRAGA UNDERGROUND
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Special+Elite&family=Rajdhani:wght@500;600;700&display=swap');

    .stApp {
        background-color: #05070c !important;
        background: linear-gradient(135deg, #020408 0%, #0b0f19 50%, #111827 100%) !important;
        color: #f3f4f6 !important;
        font-family: 'Rajdhani', sans-serif !important;
        font-weight: 600;
    }

    header[data-testid="stHeader"] {
        display: none !important;
    }

    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 6rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }

    .logo-container {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
        width: 100% !important;
        margin: 0 auto 1rem auto !important;
    }

    .logo-container video {
        display: block !important;
        margin: 0 auto !important;
        max-width: 380px !important;
        width: 100% !important;
        height: auto !important;
        border-radius: 8px !important;
        object-fit: contain !important;
    }

    h1, h2, h3, h4, h5, h6 {
        font-family: 'Anton', sans-serif !important;
        color: #ffffff !important;
        letter-spacing: 1.5px !important;
        text-transform: uppercase !important;
        text-shadow: 2px 2px 0px rgba(0, 0, 0, 0.9);
    }

    .top-metrics-grid {
        display: grid !important;
        grid-template-columns: repeat(2, 1fr) !important;
        gap: 10px !important;
        width: 100% !important;
        margin-bottom: 20px !important;
    }

    .dashboard-grid {
        display: grid !important;
        grid-template-columns: repeat(2, 1fr) !important;
        gap: 12px !important;
        width: 100% !important;
        margin-bottom: 25px !important;
    }

    .custom-card {
        background: rgba(17, 24, 39, 0.85) !important;
        border-left: 4px solid #f59e0b !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 6px !important;
        padding: 12px 8px !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
        width: 100% !important;
        min-height: 85px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.6);
    }

    .card-label {
        color: #9ca3af !important;
        font-size: 0.68rem !important;
        font-weight: 700 !important;
        letter-spacing: 1px;
        text-transform: uppercase;
        margin-bottom: 4px !important;
    }

    .card-value {
        font-family: 'Anton', sans-serif !important;
        font-size: 1.15rem !important;
        letter-spacing: 1px;
        color: #38bdf8 !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 6px !important;
        background-color: transparent !important;
        border-bottom: none !important;
        justify-content: center !important;
        flex-wrap: wrap !important;
        padding-bottom: 12px;
    }

    .stTabs [data-baseweb="tab"] {
        font-family: 'Anton', sans-serif !important;
        letter-spacing: 1px;
        background: rgba(17, 24, 39, 0.9) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 4px !important;
        color: #9ca3af !important;
        font-size: 0.9rem !important;
        padding: 8px 12px !important;
    }

    .stTabs [aria-selected="true"] {
        background: #f59e0b !important;
        color: #0b0f19 !important;
        border-color: #f59e0b !important;
    }

    .heist-board {
        background: #0f172a;
        border: 2px dashed rgba(245, 158, 11, 0.4);
        border-radius: 8px;
        padding: 20px;
        box-shadow: 0 12px 35px rgba(0,0,0,0.9);
        margin-bottom: 20px;
        position: relative;
    }
    .heist-title {
        font-family: 'Anton', sans-serif;
        color: #f87171;
        font-size: 1.6rem;
        letter-spacing: 2px;
        text-transform: uppercase;
        text-align: center;
        margin-bottom: 8px;
    }
    .heist-quote {
        font-family: 'Special Elite', cursive;
        color: #e5e7eb;
        font-size: 0.95rem;
        text-align: center;
        background: rgba(0,0,0,0.4);
        padding: 10px;
        border-radius: 4px;
        border-left: 4px solid #ef4444;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# RENDER LOGO IN CIMA
# ==========================================
video_b64 = get_video_base64("logo.gif.mp4")
if video_b64:
    st.markdown(f"""
        <div class="logo-container">
            <video autoplay loop muted playsinline>
                <source src="data:video/mp4;base64,{video_b64}" type="video/mp4">
            </video>
        </div>
    """, unsafe_allow_html=True)
else:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.title("Praga Underground Tycoon")

# ==========================================
# HEADER METRICHE TYCOON & HEAT METER POLIZIA
# ==========================================
with get_connection() as conn:
    df_lotti_scorte = pd.read_sql_query("""
        SELECT p.nome, SUM(l.quantita_attuale) as qta 
        FROM lotti l 
        JOIN prodotti p ON l.prodotto_id = p.id 
        WHERE l.quantita_attuale > 0 
        GROUP BY p.nome
    """, conn)

def get_qta_prodotto(nome_prod):
    if not df_lotti_scorte.empty and nome_prod in df_lotti_scorte['nome'].values:
        val = df_lotti_scorte[df_lotti_scorte['nome'] == nome_prod]['qta'].values[0]
        return float(val)
    return 0.0

qta_skunk = get_qta_prodotto("Skunk")
qta_hash = get_qta_prodotto("Hash Dry")
qta_lemon = get_qta_prodotto("Lemon Haze")
qta_frozen = get_qta_prodotto("Frozen Hash")

grado_rep_testo = calcola_grado_reputazione(st.session_state.reputazione)
sospetto_attuale = get_sospetto()

col_m1, col_m2 = st.columns(2)
col_m1.metric("💵 Cassa Liquida", f"€ {st.session_state.soldi_cassa:,.2f}")
col_m2.metric("🚨 Sospetto Polizia (Heat)", f"{sospetto_attuale:.1f} / 100")
st.progress(int(sospetto_attuale))

st.markdown(f"""
<div class="top-metrics-grid">
    <div class="custom-card">
        <div class="card-label">📦 Scorte Magazzino</div>
        <div style="font-size: 0.62rem; font-weight: 700; margin-top: 2px; display: flex; justify-content: center; gap: 4px; flex-wrap: wrap; color: #38bdf8; line-height: 1.3;">
            <span>🌿 {qta_skunk:.1f}g</span> &bull; 
            <span>🧱 {qta_hash:.1f}g</span> &bull; 
            <span>🍋 {qta_lemon:.1f}g</span> &bull; 
            <span>❄️ {qta_frozen:.1f}g</span>
        </div>
    </div>
    <div class="custom-card">
        <div class="card-label">📅 Turno / Giorno</div>
        <div class="card-value">Giorno {st.session_state.giorno}</div>
    </div>
    <div class="custom-card">
        <div class="card-label">⚡ Energia</div>
        <div class="card-value">{st.session_state.energia}%</div>
    </div>
    <div class="custom-card">
        <div class="card-label">⭐ Rango Praga</div>
        <div style="font-size: 0.8rem; font-family: 'Anton', sans-serif; color: #f59e0b;">{grado_rep_testo}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# PULSANTE TURNO NOTTURNO & DATA MINIMAL SOTTO
# ==========================================
data_oggi = get_data_corrente_gioco()
is_fest, desc_fest = e_festivo_o_weekend(data_oggi)
data_formattata = data_oggi.strftime("%d %B %Y")

with st.container(border=True):
    col_n1, col_n2, col_n3 = st.columns([1, 2, 1])
    with col_n2:
        if st.button("🌙 Avanza Giorno (Notte Praghese)", use_container_width=True):
            set_sospetto(get_sospetto() - 8.0)
            trigger_effetto_notte()
            st.session_state.giorno += 1
            st.session_state.giorni_trascorsi_offset += 1
            st.session_state.indice_fascia_oraria = 0
            st.session_state.energia = 100
            
            st.session_state.offerta_fornitore = None
            st.session_state.fornitori_visti_oggi = 0
            st.session_state.max_fornitori_oggi = random.choice([0, 1, 1, 2])
            st.session_state.minigioco_trattativa = False
            st.session_state.ultimo_report_bot = None
            
            if st.session_state.max_fornitori_oggi > 0 and random.random() < 0.60:
                genera_offerta_fornitore_casuale()
                
            genera_cliente_in_negozio()
            genera_evento_casuale_giorno()
            aggiungi_log("🌙 Notte trascorsa a Praga. Inizia un nuovo giorno.")
            st.rerun()

    st.markdown(f"""
        <div style="text-align: center; font-family: 'Rajdhani', sans-serif; font-size: 0.78rem; font-weight: 500; color: #9ca3af; margin-top: 6px; letter-spacing: 1px;">
            {data_formattata} &bull; <span style="color: #f59e0b;">{desc_fest}</span>
        </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ==========================================
# GESTIONE EVENTI SPECIALI
# ==========================================
if st.session_state.evento_attivo:
    ev = st.session_state.evento_attivo
    with st.container(border=True):
        st.markdown(f"### {ev['titolo']}")
        st.write(ev['testo'])
        
        if ev['tipo'] == 'polizia':
            col_ev1, col_ev2, col_ev3 = st.columns(3)
            with col_ev1:
                if st.button("💰 Corrompi Poliziotto (€50)", use_container_width=True):
                    if st.session_state.soldi_cassa >= 50.0:
                        st.session_state.soldi_cassa -= 50.0
                        set_sospetto(get_sospetto() - 35.0)
                        st.success("Tangente accettata! Il livello di allerta è sceso.")
                        aggiungi_log("🚨 POLIZIA: Pagata tangente di €50.")
                        st.session_state.evento_attivo = None
                        st.rerun()
                    else:
                        st.error("Fondi insufficienti per corrompere la pattuglia!")
            with col_ev2:
                if st.button("🏃 Rischia Retata e Nascondi", use_container_width=True):
                    if random.random() < (0.60 - (get_sospetto() / 200)):
                        st.success("Sei sfuggito ai controlli di polizia nei vicoli!")
                        set_sospetto(get_sospetto() - 15.0)
                    else:
                        st.warning("Retata subita! Sequestrata parte della cassa e delle scorte!")
                        st.session_state.soldi_cassa = max(0.0, st.session_state.soldi_cassa - 80.0)
                        with get_connection() as conn:
                            conn.execute("UPDATE lotti SET quantita_attuale = MAX(0.0, quantita_attuale - 10.0) WHERE quantita_attuale > 0 LIMIT 3")
                        set_sospetto(10.0)
                    st.session_state.evento_attivo = None
                    st.rerun()
            with col_ev3:
                if st.button("🚪 Chiudi Locale per Oggi", use_container_width=True):
                    set_sospetto(get_sospetto() - 25.0)
                    st.info("Locale blindato per tutta la giornata per evitare guai.")
                    st.session_state.evento_attivo = None
                    st.rerun()

        elif ev['tipo'] == 'vip':
            col_vip1, col_vip2 = st.columns(2)
            with col_vip1:
                if st.button("✅ ACCETTA ORDINE VIP", use_container_width=True):
                    with get_connection() as conn:
                        qta_disp_vip = pd.read_sql_query("SELECT SUM(quantita_attuale) FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0", conn, params=(ev['prodotto_id'],)).iloc[0, 0]
                    qta_disp_vip = float(qta_disp_vip) if qta_disp_vip else 0.0
                    
                    if qta_disp_vip >= ev['quantita']:
                        cli_vip_obj = {"nome": "Promotore VIP Praga", "prodotto_id": ev['prodotto_id'], "prodotto_nome": ev['prodotto_nome'], "quantita_richiesta": ev['quantita']}
                        esegui_transazione_vendita(cli_vip_obj, ev['prezzo_offerto'], "Subito")
                        st.success(f"🎉 Ordine VIP completato! Incasso: €{ev['quantita'] * ev['prezzo_offerto']:.2f}")
                        st.session_state.reputazione = min(100, st.session_state.reputazione + 5)
                        st.session_state.evento_attivo = None
                        st.rerun()
                    else:
                        st.error("Scorte insufficienti per soddisfare il VIP!")
            with col_vip2:
                if st.button("❌ Rifiuta", use_container_width=True):
                    st.session_state.evento_attivo = None
                    st.rerun()

        elif ev['tipo'] == 'festival':
            if st.button("🎉 Ottimo! Sfrutta il Festival", use_container_width=True):
                st.session_state.evento_attivo = None
                st.rerun()

        else:
            if st.button("🛡️ Allontana Teppisti", use_container_width=True):
                st.success("Li hai cacciati via dal quartiere senza danni.")
                st.session_state.evento_attivo = None
                st.rerun()

# ==========================================
# SCHEDE / TAB DELL'APPLICAZIONE
# ==========================================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "💸 Cassa", 
    "👥 Pusher",
    "📊 Dashboard", 
    "🚚 Fornitori",
    "📈 Statistiche",
    "📜 Storico & Obiettivi"
])

# ------------------------------------------
# TAB 1: CASSA OPERATIVA
# ------------------------------------------
with tab1:
    col_cassa, col_ledger = st.columns([1.2, 1])
    
    with col_cassa:
        st.subheader("💸 Cassa Operativa (Praga)")
        tipo_operazione = st.radio("Seleziona Modalità", ["Incontra Cliente (Manuale)", "Automazione Turno AI", "XME (Perk)"], horizontal=True)
        
        if tipo_operazione == "Incontra Cliente (Manuale)":
            st.markdown("##### 👤 Cliente alla Cassa")
            cli_att = st.session_state.cliente_in_negozio
            if cli_att:
                with st.container(border=True):
                    st.markdown(f"### **{cli_att['nome']}** (Praga)")
                    st.write(f"• **Richiesta:** ⭐ **{cli_att['prodotto_nome']}** ({cli_att['quantita_richiesta']} g)")
                    
                    with get_connection() as conn:
                        qta_disp_query = pd.read_sql_query("SELECT SUM(quantita_attuale) FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0", conn, params=(cli_att['prodotto_id'],)).iloc[0, 0]
                        costo_lotto_ref = pd.read_sql_query("SELECT costo_acquisto_unitario FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0 ORDER BY data_carico ASC LIMIT 1", conn, params=(cli_att['prodotto_id'],))
                        
                    qta_disp_tot = float(qta_disp_query) if (qta_disp_query is not None and not pd.isna(qta_disp_query)) else 0.0
                    costo_base_u = float(costo_lotto_ref.iloc[0,0]) if not costo_lotto_ref.empty else 0.0

                    if qta_disp_tot < cli_att['quantita_richiesta']:
                        st.error(f"❌ Scorte insufficienti! (Disponibili: {qta_disp_tot:.1f}g)")
                        if st.button("👋 Congeda Cliente", use_container_width=True):
                            st.session_state.fedelta_clienti = max(0, st.session_state.fedelta_clienti - 1)
                            genera_cliente_in_negozio()
                            st.rerun()
                    else:
                        prezzo_proposto = st.number_input("Prezzo al Grammo (€/g)", min_value=0.5, value=float(cli_att['budget_max_g']), step=0.5, format="%.2f")
                        totale_proposto = prezzo_proposto * cli_att['quantita_richiesta']
                        st.write(f"**Totale:** € {totale_proposto:.2f}")

                        tipo_pagamento = st.radio("Pagamento", ["Subito", "Dopo (Credito)"], horizontal=True, key="pag_init")

                        if st.button("🤝 Vendi", use_container_width=True):
                            esegui_transazione_vendita(cli_att, prezzo_proposto, tipo_pagamento)
                            genera_cliente_in_negozio()
                            st.rerun()

        elif tipo_operazione == "Automazione Turno AI":
            idx_corrente = st.session_state.indice_fascia_oraria
            if idx_corrente >= len(FASCE_ORARIE):
                st.warning("⚠️ Hai completato tutte le 5 fasce orarie della giornata! Clicca su **'🌙 Avanza Giorno (Notte Praghese)'** in cima per continuare.")
                
                with st.container(border=True):
                    st.markdown("### 📊 RECAP TOTALE GIORNATA (FINE TURNI)")
                    
                    with get_connection() as conn:
                        data_str_oggi = data_oggi.strftime("%Y-%m-%d")
                        mov_oggi_df = pd.read_sql_query("""
                            SELECT m.*, p.nome as prodotto_nome 
                            FROM movimenti m 
                            JOIN prodotti p ON m.prodotto_id = p.id 
                            WHERE m.tipo = 'VENDITA' AND DATE(m.data) = ?
                            ORDER BY m.data DESC
                        """, conn, params=(data_str_oggi,))

                    tot_incasso_giorno = mov_oggi_df['ricavo_totale'].sum() if not mov_oggi_df.empty else 0.0
                    tot_margine_giorno = mov_oggi_df['margine'].sum() if not mov_oggi_df.empty else 0.0
                    clienti_serviti_giorno = mov_oggi_df['cliente'].nunique() if not mov_oggi_df.empty else 0
                    transazioni_totali = len(mov_oggi_df)
                    
                    col_r1, col_r2 = st.columns(2)
                    col_r1.metric("💵 Incasso Totale Giorno", f"€ {tot_incasso_giorno:,.2f}")
                    col_r2.metric("📈 Margine Netto Giorno", f"€ {tot_margine_giorno:,.2f}")
                    
                    st.write(f"• **Clienti Unici Serviti:** 👥 {clienti_serviti_giorno} (Transazioni totali: {transazioni_totali})")
                    
                    st.markdown("##### 📦 Quantità Vendute per Prodotto:")
                    if not mov_oggi_df.empty:
                        qta_per_prodotto = mov_oggi_df.groupby('prodotto_nome')['quantita'].sum().reset_index()
                        for _, row_p in qta_per_prodotto.iterrows():
                            st.write(f"&bull; **{row_p['prodotto_nome']}**: {row_p['quantita']:.1f} g")
                    else:
                        st.write("Nessuna vendita registrata oggi.")
            else:
                fascia_corrente = FASCE_ORARIE[idx_corrente]
                st.markdown(f"##### 🏪 Automazione Sales Engine (Praga Underground)")
                st.info(f"Fascia oraria corrente: **{fascia_corrente}** ({idx_corrente + 1} di 5)")
                
                strategia_bot = st.selectbox("Strategia Bot", ["Onesta / Valore di Mercato", "Aggressiva (+20%)", "Generosa (-15%)"])

                with get_connection() as conn:
                    pusher_assunti = pd.read_sql_query("SELECT * FROM pusher WHERE assunto = 1", conn)
                
                if not pusher_assunti.empty:
                    st.info(f"👥 Pusher attivi sul campo a percentuale!")

                if st.button("🚀 Avvia Turno Fascia Corrente (-20% Energia)", use_container_width=True):
                    if st.session_state.energia < 20:
                        st.error("Sei troppo stanco! Riposa.")
                    else:
                        st.session_state.energia -= 20
                        prodotti_tutti = get_prodotti_tutti_df()
                        
                        if not prodotti_tutti.empty:
                            is_f, _ = e_festivo_o_weekend(get_data_corrente_gioco())
                            moltiplicatore_festivo = 1.35 if is_f else 1.0
                            
                            base_clienti = random.randint(3, 6) if idx_corrente >= 3 else random.randint(2, 4)
                            bonus_efficienza_totale = pusher_assunti['efficienza'].sum() if not pusher_assunti.empty else 0.0
                            
                            num_clienti_tot = int((base_clienti + int(st.session_state.fedelta_clienti / 25) + int(bonus_efficienza_totale * 3)) * moltiplicatore_festivo)
                            nomi_turno_disponibili = random.sample(LISTA_NOMI_PRAGA, min(len(LISTA_NOMI_PRAGA), max(4, num_clienti_tot + 2)))
                            
                            vendite_ok = 0
                            incasso_turno = 0.0
                            vendite_prodotti_turno = {}
                            
                            for i in range(num_clienti_tot):
                                if not nomi_turno_disponibili: break
                                cli_nome = nomi_turno_disponibili.pop(0)

                                prod_req = prodotti_tutti.sample(n=1).iloc[0]
                                p_id = int(prod_req['id'])
                                p_nome = prod_req['nome']
                                val_m = float(prod_req['valore_mercato_unitario'])
                                
                                with get_connection() as conn:
                                    cursor = conn.cursor()
                                    cursor.execute("SELECT id, quantita_attuale, costo_acquisto_unitario FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0 ORDER BY data_carico ASC", (p_id,))
                                    lotti = cursor.fetchall()
                                    if not lotti: continue
                                    
                                    prezzo_bot = val_m * 1.25 if "Aggressiva" in strategia_bot else (val_m * 0.85 if "Generosa" in strategia_bot else val_m)
                                    if st.session_state.evento_attivo and st.session_state.evento_attivo['tipo'] == 'festival':
                                        prezzo_bot *= 1.2
                                        
                                    qta_req = float(random.choices([1, 2, 5, 10, 15, 20], weights=[35, 30, 20, 10, 3, 2], k=1)[0])
                                    qta_req = min(lotti[0][1], qta_req)
                                    if qta_req <= 0: continue
                                    
                                    l_id, l_qta, l_costo = lotti[0]
                                    cursor.execute("UPDATE lotti SET quantita_attuale = quantita_attuale - ? WHERE id = ?", (qta_req, l_id))
                                    ricavo = qta_req * prezzo_bot
                                    margine = ricavo - (qta_req * l_costo)
                                    
                                    if not pusher_assunti.empty:
                                        pusher_assegnato = pusher_assunti.sample(n=1).iloc[0]
                                        quota_pusher = float(pusher_assegnato['quota_trattenuta'])
                                        guadagno_pusher = ricavo * quota_pusher
                                        guadagno_boss = ricavo - guadagno_pusher
                                        note_movimento = f"Vendita tramite Pusher ({pusher_assegnato['nome']} - Trattenuta {quota_pusher*100:.0f}%, Guadagno Pusher: €{guadagno_pusher:.2f})"
                                    else:
                                        guadagno_boss = ricavo
                                        note_movimento = f"Vendita diretta gestita dal Boss"
                                    
                                    cursor.execute("""
                                        INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, ricavo_totale, costo_totale, margine, cliente, pagamento, note)
                                        VALUES (?, ?, 'VENDITA', ?, ?, ?, ?, ?, ?, 'Subito', ?)
                                    """, (p_id, l_id, qta_req, prezzo_bot, ricavo, qta_req * l_costo, margine, cli_nome, note_movimento))
                                    
                                    st.session_state.soldi_cassa += guadagno_boss
                                    incasso_turno += ricavo
                                    vendite_ok += 1
                                    vendite_prodotti_turno[p_nome] = vendite_prodotti_turno.get(p_nome, 0.0) + qta_req

                            if vendite_ok > 0:
                                st.session_state.fedelta_clienti = min(100, st.session_state.fedelta_clienti + 4)
                                set_sospetto(get_sospetto() + (vendite_ok * 0.7))
                            
                            st.session_state.ultimo_report_bot = {
                                "fascia": fascia_corrente,
                                "vendite_ok": vendite_ok,
                                "incasso": incasso_turno,
                                "vendite_prodotti": vendite_prodotti_turno
                            }

                        st.session_state.indice_fascia_oraria += 1
                        st.rerun()

            if st.session_state.ultimo_report_bot and st.session_state.indice_fascia_oraria < len(FASCE_ORARIE):
                rep_bot = st.session_state.ultimo_report_bot
                with st.container(border=True):
                    st.markdown(f"##### 📋 Report Fascia: {rep_bot['fascia']}")
                    col_rb1, col_rb2 = st.columns(2)
                    col_rb1.metric("💵 Incasso Fascia", f"€ {rep_bot['incasso']:,.2f}")
                    col_rb2.metric("👥 Clienti Serviti", rep_bot['vendite_ok'])
                    
                    st.write("##### Quantità Vendute:")
                    for prod_n, q_v in rep_bot['vendite_prodotti'].items():
                        st.write(f"&bull; **{prod_n}**: {q_v:.1f} g")

        else:
            st.markdown("##### 🧪 Uso Personale XME (+30% Energia)")
            lotti_df = get_lotti_attivi_df()
            if not lotti_df.empty:
                with st.form("form_xme"):
                    opzioni_lotto = {f"{r['prodotto']} - Lotto: {r['codice_lotto']} (Disp: {r['quantita_attuale']:,.1f} g)": r['id'] for _, r in lotti_df.iterrows()}
                    lotto_sel = st.selectbox("Lotto", list(opzioni_lotto.keys()))
                    lotto_id = opzioni_lotto[lotto_sel]
                    qta_xme = st.number_input("Quantità (g)", min_value=0.5, value=5.0, step=0.5)

                    if st.form_submit_button("Usa XME"):
                        lotto_row = lotti_df[lotti_df['id'] == lotto_id].iloc[0]
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            nuova_q = float(lotto_row['quantita_attuale']) - qta_xme
                            p_id = int(get_prodotti_tutti_df()[get_prodotti_tutti_df()['nome'] == lotto_row['prodotto']].iloc[0]['id'])
                            cursor.execute("UPDATE lotti SET quantita_attuale = ? WHERE id = ?", (nuova_q, lotto_id))
                            cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, costo_totale, margine, cliente, note) VALUES (?, ?, 'XME', ?, ?, ?, 'XME', 'Consumo Personale')", (p_id, lotto_id, qta_xme, qta_xme * float(lotto_row['costo_acquisto_unitario']), -qta_xme * float(lotto_row['costo_acquisto_unitario'])))
                        st.session_state.energia = min(100, st.session_state.energia + 30)
                        st.rerun()

    with col_ledger:
        st.subheader("📜 Registro Eventi")
        with st.container(border=True):
            for log in st.session_state.log_gioco[:8]:
                st.caption(log)

# ------------------------------------------
# TAB 2: GESTIONE PUSHER E PERSONALE
# ------------------------------------------
with tab2:
    st.subheader("👥 Gestione Pusher a Percentuale")
    st.write("I pusher lavorano senza stipendio fisso trattenendo una percentuale fissa sulle vendite in base alla loro bravura (Vojta 25%, Kamil 35%, Anetka 40%). La merce viene scalata direttamente dal magazzino centrale.")
    
    with get_connection() as conn:
        pusher_df = pd.read_sql_query("SELECT * FROM pusher", conn)
        
    for _, p in pusher_df.iterrows():
        with st.container(border=True):
            col_p1, col_p2, col_p3 = st.columns([2, 2, 1])
            col_p1.markdown(f"### **{p['nome']}**")
            col_p2.write(f"• **Trattiene (Commissione):** {p['quota_trattenuta']*100:.0f}%\n• **Efficienza / Abilità:** +{p['efficienza']*100:.0f}%")
            
            is_assunto = bool(p['assunto'])
            if is_assunto:
                if col_p3.button("Licenzia", key=f"lic_{p['id']}"):
                    with get_connection() as conn:
                        conn.execute("UPDATE pusher SET assunto = 0 WHERE id = ?", (p['id'],))
                    st.success(f"Hai licenziato {p['nome']}.")
                    st.rerun()
            else:
                if col_p3.button("Assumi", key=f"ass_{p['id']}"):
                    with get_connection() as conn:
                        conn.execute("UPDATE pusher SET assunto = 1 WHERE id = ?", (p['id'],))
                    st.success(f"Hai assunto {p['nome']}!")
                    st.rerun()

    st.markdown("---")
    st.subheader("📊 Recap Attività e Vendite della Squadra (Oggi)")
    
    with get_connection() as conn:
        mov_squadra_df = pd.read_sql_query("""
            SELECT m.*, p.nome as prodotto_nome 
            FROM movimenti m 
            JOIN prodotti p ON m.prodotto_id = p.id 
            WHERE m.tipo = 'VENDITA'
            ORDER BY m.data DESC
        """, conn)

    if not mov_squadra_df.empty:
        tot_ricavo_squadra = mov_squadra_df['ricavo_totale'].sum()
        clienti_raggiunti = mov_squadra_df['cliente'].nunique()
        tot_grammi_venduti = mov_squadra_df['quantita'].sum()
        
        ricavo_boss = 0.0
        ricavo_pusher = 0.0
        
        for _, row_m in mov_squadra_df.iterrows():
            note_m = str(row_m['note'])
            ricavo_r = float(row_m['ricavo_totale'])
            if "Pusher" in note_m:
                if "Vojta" in note_m:
                    q_pusher = ricavo_r * 0.25
                elif "Kamil" in note_m:
                    q_pusher = ricavo_r * 0.35
                elif "Anetka" in note_m:
                    q_pusher = ricavo_r * 0.40
                else:
                    q_pusher = ricavo_r * 0.30
                ricavo_pusher += q_pusher
                ricavo_boss += (ricavo_r - q_pusher)
            else:
                ricavo_boss += ricavo_r

        col_sq1, col_sq2, col_sq3 = st.columns(3)
        col_sq1.metric("👥 Clienti Raggiunti", clienti_raggiunti)
        col_sq2.metric("⚖️ Grammi Venduti", f"{tot_grammi_venduti:.1f} g")
        col_sq3.metric("💰 Incasso Totale", f"€ {tot_ricavo_squadra:,.2f}")
        
        st.write(f"• **Profitto Netto Tuo (Boss):** € {ricavo_boss:,.2f}")
        st.write(f"• **Guadagni Trattenuti dai Pusher:** € {ricavo_pusher:,.2f}")
        
        st.markdown("##### 📦 Dettaglio Grammi per Prodotto:")
        qta_prod_sq = mov_squadra_df.groupby('prodotto_nome')['quantita'].sum().reset_index()
        for _, rsp in qta_prod_sq.iterrows():
            st.write(f"&bull; **{rsp['prodotto_nome']}**: {rsp['quantita']:.1f} g")
    else:
        st.info("Nessuna vendita registrata oggi dalla squadra in strada.")

# ------------------------------------------
# TAB 3: DASHBOARD & ANALYTICS
# ------------------------------------------
with tab3:
    st.subheader("📊 Dashboard Finanziaria")
    df_stato_disp = calcola_stato_magazzino(solo_disponibili=True)
    movimenti_df = get_movimenti_dettagliati_df()

    if not df_stato_disp.empty or not movimenti_df.empty:
        val_costo = df_stato_disp['valore_totale_costo'].sum() if not df_stato_disp.empty else 0
        val_mercato = df_stato_disp['valore_totale_mercato'].sum() if not df_stato_disp.empty else 0
        incasso_tot = movimenti_df[movimenti_df['tipo'] == 'VENDITA']['incasso'].sum() if not movimenti_df.empty else 0
        margine_tot = movimenti_df[movimenti_df['tipo'] == 'VENDITA']['margine'].sum() if not movimenti_df.empty else 0

        st.markdown(f"""
        <div class="dashboard-grid">
            <div class="custom-card"><div class="card-label">Valore (Costo)</div><div class="card-value">€ {val_costo:,.2f}</div></div>
            <div class="custom-card"><div class="card-label">Valore (Vendita)</div><div class="card-value">€ {val_mercato:,.2f}</div></div>
            <div class="custom-card"><div class="card-label">Incasso Totale</div><div class="card-value">€ {incasso_tot:,.2f}</div></div>
            <div class="custom-card"><div class="card-label">Margine Netto</div><div class="card-value">€ {margine_tot:,.2f}</div></div>
        </div>
        """, unsafe_allow_html=True)

# ------------------------------------------
# TAB 4: RIFORNIMENTI & FORNITORI CON TRATTATIVA
# ------------------------------------------
with tab4:
    st.subheader("🚚 Contatti Clandestini (Praga)")
    
    if st.session_state.offerta_fornitore:
        off = st.session_state.offerta_fornitore
        costo_tot = off['costo_totale']
        ha_soldi = st.session_state.soldi_cassa >= costo_tot

        st.markdown(f"""
        <div class="heist-board">
            <div class="heist-title">🎯 CONTATTO: {off['fornitore_nome'].upper()}</div>
            <div class="heist-quote">{off['fornitore_frase']}</div>
            <div style="display: flex; justify-content: space-around; text-align: center; margin-top: 15px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 15px;">
                <div>
                    <span style="font-size: 0.70rem; color: #9ca3af; text-transform: uppercase;">Merce</span><br>
                    <strong style="color: #f59e0b; font-size: 1.1rem; font-family: 'Anton', sans-serif;">{off['prodotto_nome']}</strong><br>
                    <span style="font-size: 0.65rem; color: #ef4444;">{off['tipo']}</span>
                </div>
                <div>
                    <span style="font-size: 0.70rem; color: #9ca3af; text-transform: uppercase;">Quantità Lotto</span><br>
                    <strong style="color: #38bdf8; font-size: 1.1rem; font-family: 'Anton', sans-serif;">{off['quantita']:,.1f} g</strong>
                </div>
                <div>
                    <span style="font-size: 0.70rem; color: #9ca3af; text-transform: uppercase;">Costo Unitario</span><br>
                    <strong style="color: #10b981; font-size: 1.1rem; font-family: 'Anton', sans-serif;">€ {off['costo_unitario']:.2f} / g</strong>
                </div>
            </div>
            <div style="text-align: center; margin-top: 18px; font-size: 1.25rem; font-family: 'Anton', sans-serif; color: #ffffff;">
                INVESTIMENTO INTERO: <span style="color: #f59e0b;">€ {costo_tot:,.2f}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("💼 COMPRA INTERO LOTTO", use_container_width=True, disabled=not ha_soldi):
                st.session_state.soldi_cassa -= costo_tot
                set_sospetto(get_sospetto() + 6.0)
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT OR IGNORE INTO prodotti (nome, valore_mercato_unitario) VALUES (?, ?)", (off['prodotto_nome'], off['valore_mercato_suggerito']))
                    p_id = cursor.fetchone() or cursor.execute("SELECT id FROM prodotti WHERE nome = ?", (off['prodotto_nome'],)).fetchone()[0]
                    if isinstance(p_id, tuple): p_id = p_id[0]

                    cursor.execute("""
                        INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (p_id, off['codice_lotto'], off['quantita'], off['quantita'], off['costo_unitario'], date.today(), date.today()))
                st.success("Acquisto completato!")
                st.session_state.offerta_fornitore = None
                st.session_state.minigioco_trattativa = False
                st.rerun()
        with col_b2:
            if st.button("❌ Rifiuta e Brucia Contatto", use_container_width=True):
                st.session_state.offerta_fornitore = None
                st.session_state.minigioco_trattativa = False
                st.rerun()

        st.markdown("---")
        with st.container(border=True):
            st.markdown("##### 📋 TRATTATIVA CLANDESTINA (OBIETTIVO BUDGET)")
            budget_proposto = st.number_input("Il tuo Budget da Spendere (€):", min_value=5.0, max_value=max(5.0, float(st.session_state.soldi_cassa)), value=min(50.0, float(st.session_state.soldi_cassa)), step=5.0)
            approccio = st.selectbox("Approccio Negoziazione", ["🤝 Profilo Basso / Affidabile", "😎 Bluff Tattico", "🔥 Pressing Totale"])
            
            if st.button("🎲 ESEGUI TRATTATIVA", use_container_width=True):
                tiro = random.randint(1, 100) + int(st.session_state.reputazione / 2)
                sconto = 0.93 if "Profilo" in approccio else (0.82 if "Bluff" in approccio else 0.70)
                nuovo_costo_u = round(off['costo_unitario'] * sconto, 2)
                qta_calcolata = round(budget_proposto / nuovo_costo_u, 2) if nuovo_costo_u > 0 else 0.0
                if qta_calcolata > off['quantita']:
                    qta_calcolata = float(off['quantita'])
                    budget_proposto = round(qta_calcolata * nuovo_costo_u, 2)

                st.session_state.minigioco_risultato = {
                    "budget": budget_proposto, "costo_u": nuovo_costo_u, "qta_offerta": qta_calcolata
                }
                st.rerun()

            if 'minigioco_risultato' in st.session_state and st.session_state.minigioco_risultato:
                res = st.session_state.minigioco_risultato
                st.info(f"💬 Proposta accettata: **{res['qta_offerta']}g** a **€{res['costo_u']:.2f}/g** per un totale di **€{res['budget']:.2f}**.")
                if st.button("✅ CONFERMA ACCORDO TRATTATIVA", use_container_width=True, disabled=st.session_state.soldi_cassa < res['budget']):
                    st.session_state.soldi_cassa -= res['budget']
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("INSERT OR IGNORE INTO prodotti (nome, valore_mercato_unitario) VALUES (?, ?)", (off['prodotto_nome'], off['valore_mercato_suggerito']))
                        p_id = cursor.fetchone() or cursor.execute("SELECT id FROM prodotti WHERE nome = ?", (off['prodotto_nome'],)).fetchone()[0]
                        if isinstance(p_id, tuple): p_id = p_id[0]
                        cursor.execute("""
                            INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (p_id, f"{off['codice_lotto']}-B", res['qta_offerta'], res['qta_offerta'], res['costo_u'], date.today(), date.today()))
                    st.success("Accordo concluso!")
                    st.session_state.offerta_fornitore = None
                    st.session_state.minigioco_risultato = None
                    st.rerun()
    else:
        fornitori_rimasti = st.session_state.max_fornitori_oggi - st.session_state.fornitori_visti_oggi
        if fornitori_rimasti > 0:
            if st.button("📞 Cerca Contatto Clandestino", use_container_width=True):
                genera_offerta_fornitore_casuale()
                st.rerun()
        else:
            st.warning("Nessun altro contatto disponibile oggi.")

    st.markdown("---")
    soglia_attuale = get_soglia_esaurimento()
    report_lotti_df = get_report_lotti_integrato_df(soglia_esaurimento_g=soglia_attuale)
    if not report_lotti_df.empty:
        st.dataframe(report_lotti_df, use_container_width=True, hide_index=True)

# ------------------------------------------
# TAB 5: STATISTICHE CLIENTI & DEBITI
# ------------------------------------------
with tab5:
    st.subheader("📈 Crediti Clienti")
    movimenti_df = get_movimenti_dettagliati_df()
    if not movimenti_df.empty:
        clienti_debito = movimenti_df[(movimenti_df['tipo'] == 'VENDITA') & (movimenti_df['stato_pagamento'] == 'Dopo (Credito)')]
        if not clienti_debito.empty:
            debito_per_cliente = clienti_debito.groupby('cliente')['incasso'].sum().reset_index()
            for _, r_d in debito_per_cliente.iterrows():
                col_d1, col_d2 = st.columns([3, 1])
                col_d1.write(f"**{r_d['cliente']}**: € {r_d['incasso']:,.2f}")
                if col_d2.button("Salda", key=f"s_{r_d['cliente']}"):
                    segna_debito_pagato(r_d['cliente'])
                    st.rerun()

# ------------------------------------------
# TAB 6: STORICO & OBIETTIVI CAMPAGNA
# ------------------------------------------
with tab6:
    st.subheader("🎯 Obiettivi Campagna & Condizioni di Vittoria")
    
    movimenti_df = get_movimenti_dettagliati_df()
    utile_totale = movimenti_df['margine'].sum() if not movimenti_df.empty else 0.0
    
    st.write("Raggiungi gli obiettivi per completare la tua scalata nel sottosuolo di Praga:")
    st.progress(min(1.0, utile_totale / 10000.0))
    st.write(f"• **Utile Netto Attuale:** € {utile_totale:,.2f} / € 10,000.00 obiettivo campagna")
    st.write(f"• **Sospetto Polizia Attuale:** {get_sospetto():.1f}% (Mantienilo sotto il 50% per evitare retate)")

    st.markdown("---")
    st.subheader("📜 Storico Completo")
    if not movimenti_df.empty:
        st.dataframe(movimenti_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    with st.expander("⚠️ Danger Zone: Reset Partita"):
        if st.button("💥 Reset Totale"):
            reset_completo_nuova_partita()
            st.rerun()
