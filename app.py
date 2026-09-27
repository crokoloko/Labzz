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
    page_title="LaBzz - Tycoon Management",
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

init_db()

FASCE_ORARIE = [
    "🌅 1. Mattina (08:00 - 11:30)", 
    "☀️ 2. Mezzogiorno (11:30 - 15:00)", 
    "🌇 3. Pomeriggio (15:00 - 18:30)", 
    "🌙 4. Sera (18:30 - 22:00)", 
    "🌌 5. Notte (22:00 - 02:00)"
]

def get_data_corrente_gioco():
    data_base = date(2026, 9, 27)
    giorni_trascorsi = st.session_state.giorni_trascorsi_offset
    return data_base + timedelta(days=giorni_trascorsi)

def e_festivo_o_weekend(data_rif):
    if data_rif.weekday() >= 5:
        return True, "Fine Settimana (Weekend 🎉)"
    
    feste_fisse = [(1, 1), (6, 1), (25, 4), (1, 5), (2, 6), (15, 8), (1, 11), (8, 12), (25, 12), (26, 12)]
    if (data_rif.day, data_rif.month) in feste_fisse:
        return True, "Festività Nazionale 🇮🇹"
        
    return False, "Giorno Lavorativo 💼"

def genera_codice_lotto_automatico(data_riferimento=None):
    if data_riferimento is None:
        data_riferimento = get_data_corrente_gioco()
    
    giorno = data_riferimento.strftime("%d").lstrip("0")
    MESE_INIZIALI = ['g', 'f', 'm', 'a', 'm', 'g', 'l', 'a', 's', 'o', 'n', 'd']
    iniziale_mese = MESE_INIZIALI[data_riferimento.month - 1]
    anno_2_cifre = data_riferimento.strftime("%y")
    
    return f"{giorno}{iniziale_mese}{anno_2_cifre}"

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
        return "🌱 Principiante di Quartiere"
    elif rep < 60:
        return "🥈 Spacciatore Rispettato"
    elif rep < 85:
        return "🥇 Boss della Zona"
    else:
        return "👑 Re del Quartiere"

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
    ">🌙 PASSAGGIO DELLA NOTTE... ALBA IN ARRIVO ☀️</div>
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
    {"nome": "Don Cornetto", "frase": "«Un'offerta che non puoi rifiutare... o finisci a fare i cappucci!»"},
    {"nome": "Tony Pesto", "frase": "«O compri questo stock o stasera le cotolette le fai coi denti!»"},
    {"nome": "Al Cacio", "frase": "«Robina fresca fresca di contrabbando, scesa dal camion mezz'ora fa.»"},
    {"nome": "Franky 'Cinque Dita'", "frase": "«Guarda che qualità, sfiorala soltanto e ti senti già ricchissimo!»"},
    {"nome": "Peppe 'u Scannatore", "frase": "«Vedi di fare in fretta prima che arrivi la finanza...»"},
    {"nome": "Luigi 'O Calibro", "frase": "«Prezzo da amico, ma non farmi domande su dove l'ho preso.»"},
    {"nome": "Gaetano 'Er Siringa'", "frase": "«Trattativa pulita, niente sbirri, solo contanti e saluti.»"},
    {"nome": "Mimmo 'Er Cipolla'", "frase": "«Questa ti fa piangere da quanto è buona. Prendi prima che cambi idea!»"}
]

def genera_offerta_fornitore_casuale():
    if st.session_state.fornitori_visti_oggi >= st.session_state.max_fornitori_oggi:
        st.info("Per oggi non ci sono altri contatti disponibili.")
        return

    st.session_state.fornitori_visti_oggi += 1
    gangster = random.choice(GANGSTER_FORNITORI)
    
    giorno_corrente = st.session_state.giorno
    moltiplicatore_giornaliero = 1.0 + min(2.5, (giorno_corrente - 1) * 0.18)
    
    rischio_sola = random.random() < (0.20 + min(0.30, giorno_corrente * 0.02))
    
    if rischio_sola:
        tipo_offerta = "⚠️ ATTENZIONE: Sospetta 'Sola' / Pacco!"
        p_nome = "Skunk"
        qta = float(random.choice([80, 100, 150, 200]) * moltiplicatore_giornaliero)
        costo_u = round(random.uniform(3.00, 4.20), 2)
        valore_mercato_suggerito = 7.0
        gangster_frase_sola = f"«{gangster['nome']} ti guarda con un ghigno strano...» " + gangster['frase']
    else:
        varieta_scelta = random.choice(["Skunk", "Hash Dry", "Lemon Haze", "Frozen Hash"])
        
        if varieta_scelta == "Skunk":
            p_nome = "Skunk"
            qta = float(random.choice([60, 100, 150, 200]) * moltiplicatore_giornaliero)
            costo_u = round(random.uniform(2.50, 3.50), 2)
            valore_mercato_suggerito = 7.0
            tipo_offerta = "🌿 Skunk Economica (Bassa Qualità)"

        elif varieta_scelta == "Hash Dry":
            p_nome = "Hash Dry"
            qta = float(random.choice([40, 80, 120, 160]) * moltiplicatore_giornaliero)
            costo_u = round(random.uniform(4.00, 5.50), 2)
            valore_mercato_suggerito = 10.0
            tipo_offerta = "🧱 Hash Dry Commerciale (Buona Qualità)"

        elif varieta_scelta == "Lemon Haze":
            p_nome = "Lemon Haze"
            qta = float(random.choice([30, 60, 100, 130]) * moltiplicatore_giornaliero)
            costo_u = round(random.uniform(6.50, 8.50), 2)
            valore_mercato_suggerito = 14.0
            tipo_offerta = "🍋 Lemon Haze (Ottima Qualità)"

        else:
            p_nome = "Frozen Hash"
            qta = float(random.choice([20, 40, 70, 100]) * moltiplicatore_giornaliero)
            costo_u = round(random.uniform(10.00, 13.50), 2)
            valore_mercato_suggerito = 22.0
            tipo_offerta = "❄️ Frozen Hash (Top del Mercato)"

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
        "codice_lotto": f"OFF-{random.randint(100,999)}"
    }

def genera_cliente_in_negozio():
    prodotti_tutti = get_prodotti_tutti_df()
    if not prodotti_tutti.empty:
        prod = prodotti_tutti.sample(n=1).iloc[0]
        nomi_clienti = ["Marco", "Elena", "Giuseppe", "Sara", "Luca", "Chiara", "ClienteVIP", "Matteo", "Valentina"]
        nome_c = random.choice(nomi_clienti)
        
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
    if random.random() < 0.38:
        evento_tipo = random.choice(["polizia", "vip", "tossici"])
        
        if evento_tipo == "polizia":
            st.session_state.evento_attivo = {
                "tipo": "polizia",
                "titolo": "🚨 BLITZ / POSTO DI BLOCCO DELLA FINANZA!",
                "testo": "Voci di corridoio dicono che le forze dell'ordine stanno setacciando la zona con controlli a tappeto vicino al locale. Tensione alle stelle!"
            }
        elif evento_tipo == "vip":
            prodotti_disp = get_prodotti_disponibili_df()
            if not prodotti_disp.empty:
                prod_vip = prodotti_disp.sample(n=1).iloc[0]
                qta_vip = float(random.choice([5, 10, 15]))
                prezzo_vip = float(prod_vip['valore_mercato_unitario']) * 1.40
                st.session_state.evento_attivo = {
                    "tipo": "vip",
                    "titolo": "📱 NOTIFICA VIP URGENTE",
                    "testo": f"Un cliente VIP misterioso ti ha scritto sul telefono: «Mi servono urgentemente **{qta_vip}g di {prod_vip['nome']}**. Ti pago a peso d'oro (**€{prezzo_vip:.2f}/g**) se me li procuri oggi stesso!»",
                    "prodotto_id": int(prod_vip['id']),
                    "prodotto_nome": prod_vip['nome'],
                    "quantita": qta_vip,
                    "prezzo_offerto": prezzo_vip
                }
            else:
                st.session_state.evento_attivo = None
        else:
            st.session_state.evento_attivo = {
                "tipo": "tossici",
                "titolo": "🧟 IRRUZIONE DI TOSSICI IN ASTINENZA!",
                "testo": "Un gruppo di disperati in astinenza si aggira con fare minaccioso intorno al locale urlando e strattonando la porta. Vogliono rubare scorte perché non hanno un centesimo!"
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
    aggiungi_log(f"✅ VENDITA: {cli_att['nome']} ha comprato {cli_att['quantita_richiesta']}g di '{cli_att['prodotto_nome']}' a €{prezzo_per_g:.2f}/g (+€{totale_incasso:.2f})")
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
    st.session_state.log_gioco = ["🎮 Benvenuto nel mondo Tycoon! Capitale iniziale: €200."]
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
        
        cursor.execute("INSERT INTO prodotti (nome, valore_mercato_unitario, scorta_minima_g) VALUES ('Skunk', 7.0, 20.0);")
        p_id = cursor.lastrowid
        cursor.execute("INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico) VALUES (?, 'START-01', 50.0, 50.0, 2.50, ?, ?);", (p_id, date.today(), date.today()))
        l_id = cursor.lastrowid
        cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, costo_totale, cliente, note) VALUES (?, ?, 'CARICO', 50.0, 125.0, 'Fornitore Iniziale', 'Stock Start')", (p_id, l_id))
    
    st.session_state.soldi_cassa = 200.0
    st.session_state.giorno = 1
    st.session_state.giorni_trascorsi_offset = 0
    st.session_state.indice_fascia_oraria = 0
    st.session_state.energia = 100
    st.session_state.reputazione = 15
    st.session_state.fedelta_clienti = 10
    st.session_state.log_gioco = ["✨ Nuova Partita Iniziata! Reset completo eseguito. Budget: €200."]
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
# INIEZIONE CSS CUSTOM — STILE GTA / LAVAGNA CRIMINALE
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Special+Elite&family=Rajdhani:wght@500;600;700&display=swap');

    .stApp {
        background-color: #0b0f19 !important;
        background: linear-gradient(135deg, #05070c 0%, #0b0f19 50%, #111827 100%) !important;
        color: #f3f4f6 !important;
        font-family: 'Rajdhani', sans-serif !important;
        font-weight: 600;
    }

    header[data-testid="stHeader"] {
        display: none !important;
    }

    .block-container {
        padding-top: 2.2rem !important;
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
        max-width: 400px !important;
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
        text-shadow: 2px 2px 0px rgba(0, 0, 0, 0.8);
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
        padding: 10px 8px !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
        width: 100% !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    }

    .card-label {
        color: #9ca3af !important;
        font-size: 0.70rem !important;
        font-weight: 700 !important;
        letter-spacing: 1px;
        text-transform: uppercase;
        margin-bottom: 2px !important;
    }

    .card-value {
        font-family: 'Anton', sans-serif !important;
        font-size: 1.2rem !important;
        letter-spacing: 1px;
        color: #38bdf8 !important;
    }

    .card-subtext {
        font-size: 0.70rem !important;
        color: #fbbf24 !important;
        font-weight: 700 !important;
        margin-top: 2px !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px !important;
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
        font-size: 0.95rem !important;
        padding: 8px 14px !important;
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
        st.title("LaBzz Tycoon")

# ==========================================
# HEADER METRICHE TYCOON GRIGLIA COMPATTA
# ==========================================
with get_connection() as conn:
    df_lotti_scorte = pd.read_sql_query("""
        SELECT p.nome, SUM(l.quantita_attuale) as qta 
        FROM lotti l 
        JOIN prodotti p ON l.prodotto_id = p.id 
        WHERE l.quantita_attuale > 0 
        GROUP BY p.nome
    """, conn)

qta_totale_magazzino = df_lotti_scorte['qta'].sum() if not df_lotti_scorte.empty else 0.0

# Estrazione quantità per singola varietà con i relativi simbolotti
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

st.markdown(f"""
<div class="top-metrics-grid">
    <div class="custom-card">
        <div class="card-label">💵 Cassa Liquida</div>
        <div class="card-value">€ {st.session_state.soldi_cassa:,.2f}</div>
    </div>
    <div class="custom-card">
        <div class="card-label">📦 Scorte Magazzino</div>
        <div class="card-value">{qta_totale_magazzino:.1f} g</div>
        <div class="card-subtext" style="font-size: 0.62rem; color: #9ca3af; margin-top: 4px; display: flex; justify-content: center; gap: 6px; flex-wrap: wrap;">
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
    <div class="custom-card" style="grid-column: span 2;">
        <div class="card-label">⭐ Reputazione e Rango</div>
        <div class="card-value">{st.session_state.reputazione} / 100 ({grado_rep_testo})</div>
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
        if st.button("🌙 Riposa e Passa al Giorno Successivo", use_container_width=True):
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
            aggiungi_log(f"🌙 Giorno {st.session_state.giorno} ({data_formattata}) iniziato. Energia 100%. Fornitori disponibili: {st.session_state.max_fornitori_oggi}")
            st.rerun()

    st.markdown(f"""
        <div style="text-align: center; font-family: 'Rajdhani', sans-serif; font-size: 0.78rem; font-weight: 500; color: #9ca3af; margin-top: 6px; letter-spacing: 1px;">
            {data_formattata} &bull; <span style="color: #f59e0b;">{desc_fest}</span>
        </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ==========================================
# GESTIONE EVENTI SPECIALI (POLIZIA / VIP / TOSSICI) IN EVIDENZA
# ==========================================
if st.session_state.evento_attivo:
    ev = st.session_state.evento_attivo
    with st.container(border=True):
        st.markdown(f"### {ev['titolo']}")
        st.write(ev['testo'])
        
        if ev['tipo'] == 'polizia':
            col_ev1, col_ev2, col_ev3 = st.columns(3)
            with col_ev1:
                if st.button("💰 Paga Tangente (€45)", use_container_width=True):
                    if st.session_state.soldi_cassa >= 45.0:
                        st.session_state.soldi_cassa -= 45.0
                        st.success("Hai corrotto la pattuglia! Sgomberati i controlli.")
                        aggiungi_log("🚨 POLIZIA: Pagata tangente di €45 per evitare guai.")
                        st.session_state.evento_attivo = None
                        st.rerun()
                    else:
                        st.error("Non hai abbastanza contanti per la tangente!")
            with col_ev2:
                if st.button("🏃 Rischia e Nascondi Merce", use_container_width=True):
                    if random.random() < 0.55:
                        st.success("Sei riuscito a nascondere tutto in tempo! Sgommati senza danni.")
                        aggiungi_log("🚨 POLIZIA: Controlli superati nascondendo la merce.")
                    else:
                        st.warning("Ti hanno perquisito il magazzino e sequestrato un po' di scorte!")
                        aggiungi_log("🚨 POLIZIA: Perquisizione subita! Sequestro parziale di scorte.")
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("UPDATE lotti SET quantita_attuale = MAX(0.0, quantita_attuale - 8.0) WHERE quantita_attuale > 0 LIMIT 3")
                    st.session_state.evento_attivo = None
                    st.rerun()
            with col_ev3:
                if st.button("🚪 Chiudi Locale per Oggi", use_container_width=True):
                    st.info("Hai tenuto chiuso per evitare rogne. Giornata persa.")
                    aggiungi_log("🚨 POLIZIA: Locale chiuso per l'intera giornata.")
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
                        cli_vip_obj = {"nome": "Cliente VIP", "prodotto_id": ev['prodotto_id'], "prodotto_nome": ev['prodotto_nome'], "quantita_richiesta": ev['quantita']}
                        esegui_transazione_vendita(cli_vip_obj, ev['prezzo_offerto'], "Subito")
                        st.success(f"🎉 Ordine VIP completato con successo! Incasso super: €{ev['quantita'] * ev['prezzo_offerto']:.2f}")
                        st.session_state.reputazione = min(100, st.session_state.reputazione + 4)
                        aggiungi_log(f"📱 VIP: Completato ordine speciale di {ev['quantita']}g di {ev['prodotto_nome']}.")
                        st.session_state.evento_attivo = None
                        st.rerun()
                    else:
                        st.error(f"Non hai abbastanza scorte di {ev['prodotto_nome']} (Disponibili: {qta_disp_vip:.1f}g)!")
            with col_vip2:
                if st.button("❌ RIFIUTA ORDINE", use_container_width=True):
                    st.info("Hai declinato l'offerta VIP.")
                    st.session_state.evento_attivo = None
                    st.rerun()

        elif ev['tipo'] == 'tossici':
            col_tox1, col_tox2 = st.columns(2)
            with col_tox1:
                if st.button("🛡️ Affrontali e Difendi il Locale", use_container_width=True):
                    if random.random() < 0.60:
                        st.success("Sei riuscito a cacciarli via a malo modo senza subire perdite!")
                        aggiungi_log("🧟 TOSSICI: Cacciati via con successo dal locale.")
                    else:
                        st.warning("Hanno sfondato e arraffato un po' di merce prima di darsi alla fuga!")
                        aggiungi_log("🧟 TOSSICI: Subito saccheggio! Perdita di scorte dal magazzino.")
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("UPDATE lotti SET quantita_attuale = MAX(0.0, quantita_attuale - 10.0) WHERE quantita_attuale > 0 LIMIT 2")
                    st.session_state.evento_attivo = None
                    st.rerun()
            with col_tox2:
                if st.button("🏃 Scappa e Lascia Fare", use_container_width=True):
                    st.error("I tossici sono entrati e hanno ripulito parte delle scorte senza incontrare resistenza!")
                    aggiungi_log("🧟 TOSSICI: Locale saccheggiato in tua assenza.")
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE lotti SET quantita_attuale = MAX(0.0, quantita_attuale - 12.0) WHERE quantita_attuale > 0 LIMIT 2")
                    st.session_state.evento_attivo = None
                    st.rerun()

# ==========================================
# SCHEDE / TAB DELL'APPLICAZIONE
# ==========================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "💸 Cassa", 
    "📊 Dashboard", 
    "🚚 Rifornimenti & Fornitori",
    "📈 Statistiche",
    "📜 Report & Storico"
])

# ------------------------------------------
# TAB 1: CASSA OPERATIVA
# ------------------------------------------
with tab1:
    col_cassa, col_ledger = st.columns([1.2, 1])
    
    with col_cassa:
        st.subheader("💸 Cassa Operativa")
        
        tipo_operazione = st.radio("Seleziona Modalità", ["Incontra Cliente (Manuale)", "Automazione Turno AI", "XME (Perk)"], horizontal=True)
        
        if tipo_operazione == "Incontra Cliente (Manuale)":
            st.markdown("##### 👤 Cliente Attualmente alla Cassa")
            
            cli_att = st.session_state.cliente_in_negozio
            if cli_att:
                with st.container(border=True):
                    st.markdown(f"### **{cli_att['nome']}** è qui per comprare!")
                    st.write(f"• **Varietà Richiesta:** ⭐ **{cli_att['prodotto_nome']}**")
                    st.write(f"• **Quantità Richiesta:** {cli_att['quantita_richiesta']} g")
                    
                    with get_connection() as conn:
                        qta_disp_query = pd.read_sql_query("SELECT SUM(quantita_attuale) FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0", conn, params=(cli_att['prodotto_id'],)).iloc[0, 0]
                        costo_lotto_ref = pd.read_sql_query("SELECT costo_acquisto_unitario FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0 ORDER BY data_carico ASC LIMIT 1", conn, params=(cli_att['prodotto_id'],))
                        
                    qta_disp_tot = float(qta_disp_query) if (qta_disp_query is not None and not pd.isna(qta_disp_query)) else 0.0
                    costo_base_u = float(costo_lotto_ref.iloc[0,0]) if not costo_lotto_ref.empty else 0.0

                    if qta_disp_tot < cli_att['quantita_richiesta']:
                        st.error(f"❌ NON HAI QUESTO PRODOTTO IN MAGAZZINO! (Disponibili: {qta_disp_tot:.1f}g di {cli_att['prodotto_nome']})")
                        st.write(f"«Pessimo servizio! Volevo proprio della **{cli_att['prodotto_nome']}**. Tornerò quando ti sarai rifornito!»")
                        
                        if st.button("👋 Congeda Cliente Deluso", use_container_width=True):
                            st.session_state.fedelta_clienti = max(0, st.session_state.fedelta_clienti - 1)
                            aggiungi_log(f"⚠️ VENDITA FALLITA: {cli_att['nome']} voleva {cli_att['prodotto_nome']} ma non ne avevi abbastanza.")
                            genera_cliente_in_negozio()
                            st.rerun()

                    else:
                        st.info(f"Disponibilità in magazzino: {qta_disp_tot:.1f} g di {cli_att['prodotto_nome']}")
                        
                        if cli_att.get("controfferta_attiva", False):
                            st.warning(f"🗣️ **CONTROFFERTA DI {cli_att['nome'].upper()}:**")
                            st.write(f"«Troppo caro! Io ti offro **€ {cli_att['budget_max_g']:.2f} / g** per {cli_att['quantita_richiesta']}g di **{cli_att['prodotto_nome']}**.»")
                            
                            incasso_contro = cli_att['budget_max_g'] * cli_att['quantita_richiesta']
                            costo_tot_contro = costo_base_u * cli_att['quantita_richiesta']
                            margine_contro = incasso_contro - costo_tot_contro
                            
                            st.markdown("##### 🧮 I tuoi conti sulla controfferta:")
                            col_c1, col_c2, col_c3 = st.columns(3)
                            col_c1.metric("Incasso Totale", f"€ {incasso_contro:.2f}")
                            col_c2.metric("Costo Stock", f"€ {costo_tot_contro:.2f}")
                            col_c3.metric("Guadagno Netto", f"€ {margine_contro:.2f}")

                            tipo_pagamento = st.radio("Modalità Pagamento", ["Subito", "Dopo (Credito)"], horizontal=True, key="pag_contro")

                            col_co1, col_co2 = st.columns(2)
                            with col_co1:
                                if st.button("✅ ACCETTA CONTROFFERTA", use_container_width=True):
                                    esegui_transazione_vendita(cli_att, cli_att['budget_max_g'], tipo_pagamento)
                                    st.success("Accettata la controfferta del cliente!")
                                    genera_cliente_in_negozio()
                                    st.rerun()
                            with col_co2:
                                if st.button("❌ RIFIUTA E MANDA VIA", use_container_width=True):
                                    st.session_state.fedelta_clienti = max(0, st.session_state.fedelta_clienti - 2)
                                    aggiungi_log(f"❌ RIFIUTATO: Rifiutata controfferta di {cli_att['nome']}")
                                    st.info("Hai rifiutato la controfferta. Il cliente è andato via.")
                                    genera_cliente_in_negozio()
                                    st.rerun()

                        else:
                            prezzo_proposto = st.number_input("Imposta il Tuo Prezzo al Grammo (€/g)", min_value=0.5, value=float(cli_att['budget_max_g']), step=0.5, format="%.2f")
                            totale_proposto = prezzo_proposto * cli_att['quantita_richiesta']
                            st.write(f"**Totale Incasso Proposto:** € {totale_proposto:.2f}")

                            tipo_pagamento = st.radio("Modalità Pagamento", ["Subito", "Dopo (Credito)"], horizontal=True, key="pag_init")

                            col_act1, col_act2 = st.columns(2)
                            with col_act1:
                                if st.button("🤝 Proponi Offerta e Vendi", use_container_width=True):
                                    if prezzo_proposto <= cli_att['budget_max_g']:
                                        esegui_transazione_vendita(cli_att, prezzo_proposto, tipo_pagamento)
                                        st.success(f"🎉 {cli_att['nome']} ha ACCETTATO!")
                                        genera_cliente_in_negozio()
                                        st.rerun()
                                    else:
                                        st.session_state.cliente_in_negozio['controfferta_attiva'] = True
                                        st.warning(f"⚠️ {cli_att['nome']} ritiene la cifra alta e ti sta facendo una controfferta!")
                                        st.rerun()

                            with col_act2:
                                if st.button("🚪 Rifiuta / Prossimo", use_container_width=True):
                                    st.info("Cliente congedato.")
                                    genera_cliente_in_negozio()
                                    st.rerun()

        elif tipo_operazione == "Automazione Turno AI":
            idx_corrente = st.session_state.indice_fascia_oraria

            if idx_corrente >= len(FASCE_ORARIE):
                st.warning("⚠️ Hai completato tutte le 5 fasce orarie della giornata! Clicca su **'🌙 Riposa e Passa al Giorno Successivo'** in cima per continuare.")
                
                # --- RECAP COMPLETO DELLA GIORNATA APPENA CONCLUSA ---
                with st.container(border=True):
                    st.markdown("### 📊 RECAP TOTALE GIORNATA (FINE TURNI)")
                    
                    with get_connection() as conn:
                        mov_oggi_df = pd.read_sql_query("""
                            SELECT m.*, p.nome as prodotto_nome 
                            FROM movimenti m 
                            JOIN prodotti p ON m.prodotto_id = p.id 
                            WHERE m.tipo = 'VENDITA'
                            ORDER BY m.data DESC LIMIT 15
                        """, conn)

                    tot_incasso_giorno = mov_oggi_df['ricavo_totale'].sum() if not mov_oggi_df.empty else 0.0
                    tot_margine_giorno = mov_oggi_df['margine'].sum() if not mov_oggi_df.empty else 0.0
                    clienti_serviti_giorno = mov_oggi_df['cliente'].nunique() if not mov_oggi_df.empty else 0
                    transazioni_totali = len(mov_oggi_df)
                    
                    qta_frozen_giorno = mov_oggi_df[mov_oggi_df['prodotto_nome'].str.contains("Frozen Hash", case=False, na=False)]['quantita'].sum() if not mov_oggi_df.empty else 0.0
                    qta_altre_giorno = mov_oggi_df[~mov_oggi_df['prodotto_nome'].str.contains("Frozen Hash", case=False, na=False)]['quantita'].sum() if not mov_oggi_df.empty else 0.0

                    col_r1, col_r2 = st.columns(2)
                    col_r1.metric("💵 Incasso Totale Giorno", f"€ {tot_incasso_giorno:,.2f}")
                    col_r2.metric("📈 Margine Netto Giorno", f"€ {tot_margine_giorno:,.2f}")
                    
                    st.write(f"• **Clienti Unici Serviti:** 👥 {clienti_serviti_giorno} (Transazioni totali: {transazioni_totali})")
                    st.write(f"• **Frozen Hash Venduto:** ❄️ {qta_frozen_giorno:.1f} g")
                    st.write(f"• **Altre Varietà Vendute:** 📦 {qta_altre_giorno:.1f} g")
                    
                    if not mov_oggi_df.empty:
                        st.markdown("##### 🛒 Dettaglio Ultimi Clienti Serviti Oggi:")
                        st.dataframe(mov_oggi_df[['data', 'cliente', 'prodotto_nome', 'quantita', 'ricavo_totale']], use_container_width=True, hide_index=True)
            else:
                fascia_corrente = FASCE_ORARIE[idx_corrente]

                st.markdown(f"##### 🏪 Automazione Sales Engine")
                st.info(f"Fascia oraria corrente: **{fascia_corrente}** ({idx_corrente + 1} di 5)")

                strategia_bot = st.selectbox("Strategia Bot", ["Onesta / Valore di Mercato", "Aggressiva (+20%)", "Generosa (-15%)"])

                if st.button("🚀 Avvia Turno Fascia Corrente (-20% Energia)", use_container_width=True):
                    if st.session_state.energia < 20:
                        st.error("Sei troppo stanco! Riposa.")
                    else:
                        st.session_state.energia -= 20
                        prodotti_tutti = get_prodotti_tutti_df()
                        
                        if not prodotti_tutti.empty:
                            is_f, _ = e_festivo_o_weekend(get_data_corrente_gioco())
                            moltiplicatore_festivo = 1.45 if is_f else 1.0
                            
                            if idx_corrente >= 3:
                                base_clienti = random.randint(6, 10)
                            elif idx_corrente == 1:
                                base_clienti = random.randint(4, 7)
                            else:
                                base_clienti = random.randint(3, 6)
                                
                            num_clienti_tot = int((base_clienti + int(st.session_state.fedelta_clienti / 15)) * moltiplicatore_festivo)
                            clienti_nomi = ["Marco", "Elena", "Giuseppe", "Sara", "Luca", "Chiara", "ClienteVIP", "Matteo", "Valentina"]
                            
                            vendite_ok = 0
                            incasso_turno = 0.0
                            qta_frozen_turno = 0.0
                            qta_altre_turno = 0.0
                            clienti_contrattato = 0
                            
                            for _ in range(num_clienti_tot):
                                prod_req = prodotti_tutti.sample(n=1).iloc[0]
                                p_id = int(prod_req['id'])
                                p_nome = prod_req['nome']
                                val_m = float(prod_req['valore_mercato_unitario'])
                                cli_nome = random.choice(clienti_nomi)
                                
                                is_frozen = "Frozen Hash" in p_nome
                                
                                with get_connection() as conn:
                                    cursor = conn.cursor()
                                    cursor.execute("SELECT id, quantita_attuale, costo_acquisto_unitario FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0 ORDER BY data_carico ASC", (p_id,))
                                    lotti = cursor.fetchall()
                                    
                                    if not lotti: continue
                                    
                                    prezzo_bot = val_m * 1.25 if "Aggressiva" in strategia_bot else (val_m * 0.85 if "Generosa" in strategia_bot else val_m)
                                    budget_cli = val_m * random.uniform(0.85, 1.35) * (1 + (st.session_state.fedelta_clienti / 200))
                                    
                                    if prezzo_bot > budget_cli and prezzo_bot <= budget_cli * 1.15:
                                        clienti_contrattato += 1
                                        if random.random() < 0.60:
                                            prezzo_bot = budget_cli
                                        else:
                                            continue
                                    elif prezzo_bot > budget_cli * 1.15:
                                        clienti_contrattato += 1
                                        continue

                                    qta_req = float(random.choices([1, 2, 5, 10, 15, 20], weights=[30, 30, 25, 10, 3, 2], k=1)[0])
                                    qta_req = min(lotti[0][1], qta_req)
                                    if qta_req <= 0: continue
                                    
                                    l_id, l_qta, l_costo = lotti[0]
                                    cursor.execute("UPDATE lotti SET quantita_attuale = quantita_attuale - ? WHERE id = ?", (qta_req, l_id))
                                    ricavo = qta_req * prezzo_bot
                                    margine = ricavo - (qta_req * l_costo)
                                    
                                    cursor.execute("""
                                        INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, ricavo_totale, costo_totale, margine, cliente, pagamento)
                                        VALUES (?, ?, 'VENDITA', ?, ?, ?, ?, ?, ?, 'Subito')
                                    """, (p_id, l_id, qta_req, prezzo_bot, ricavo, qta_req * l_costo, margine, cli_nome))
                                    
                                    st.session_state.soldi_cassa += ricavo
                                    incasso_turno += ricavo
                                    vendite_ok += 1
                                    
                                    if is_frozen:
                                        qta_frozen_turno += qta_req
                                    else:
                                        qta_altre_turno += qta_req
                                        
                                    aggiungi_log(f"✅ BOT ({fascia_corrente[:10]}): {cli_nome} ha comprato {qta_req}g di '{p_nome}' (+€{ricavo:.2f})")

                            if vendite_ok > 0:
                                st.session_state.fedelta_clienti = min(100, st.session_state.fedelta_clienti + 4)
                                st.session_state.reputazione = min(100, st.session_state.reputazione + 2)
                            
                            st.session_state.ultimo_report_bot = {
                                "fascia": fascia_corrente,
                                "vendite_ok": vendite_ok,
                                "incasso": incasso_turno,
                                "qta_frozen": qta_frozen_turno,
                                "qta_altre": qta_altre_turno,
                                "contrattati": clienti_contrattato
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
                    
                    st.write(f"• **Frozen Hash Venduto:** ❄️ {rep_bot['qta_frozen']:.1f} g")
                    st.write(f"• **Altre Varietà Vendute:** 📦 {rep_bot['qta_altre']:.1f} g")
                    st.write(f"• **Contrattazioni:** 💬 {rep_bot['contrattati']}")

        elif tipo_operazione == "XME":
            st.markdown("##### 🧪 Registra Uso Personale XME (+30% Energia)")
            lotti_df = get_lotti_attivi_df()
            if not lotti_df.empty:
                with st.form("form_xme"):
                    opzioni_lotto = {f"{r['prodotto']} - Lotto: {r['codice_lotto']} (Disp: {r['quantita_attuale']:,.1f} g)": r['id'] for _, r in lotti_df.iterrows()}
                    lotto_sel = st.selectbox("Seleziona Lotto", list(opzioni_lotto.keys()))
                    lotto_id = opzioni_lotto[lotto_sel]
                    qta_xme = st.number_input("Quantità (g)", min_value=0.5, value=5.0, step=0.5)

                    if st.form_submit_button("Conferma Uscita XME"):
                        lotto_row = lotti_df[lotti_df['id'] == lotto_id].iloc[0]
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            nuova_q = float(lotto_row['quantita_attuale']) - qta_xme
                            p_id = int(get_prodotti_tutti_df()[get_prodotti_tutti_df()['nome'] == lotto_row['prodotto']].iloc[0]['id'])
                            cursor.execute("UPDATE lotti SET quantita_attuale = ? WHERE id = ?", (nuova_q, lotto_id))
                            cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, costo_totale, margine, cliente, note) VALUES (?, ?, 'XME', ?, ?, ?, 'XME', 'Consumo Perk')", (p_id, lotto_id, qta_xme, qta_xme * float(lotto_row['costo_acquisto_unitario']), -qta_xme * float(lotto_row['costo_acquisto_unitario'])))
                        
                        st.session_state.energia = min(100, st.session_state.energia + 30)
                        aggiungi_log(f"🧪 XME: Consumati {qta_xme}g dal lotto.")
                        st.rerun()

    # --------------------------------------
    # COLONNA 2: REGISTRO EVENTI SOPRA, MOVIMENTI LIVE (LEDGER) SOTTO
    # --------------------------------------
    with col_ledger:
        st.subheader("📜 Registro Eventi Turno")
        with st.container(border=True):
            for log in st.session_state.log_gioco[:10]:
                st.caption(log)

        st.markdown("---")
        st.subheader("📖 Ledger & Movimenti Live")
        
        movimenti_df = get_movimenti_dettagliati_df()
        if not movimenti_df.empty:
            st.dataframe(
                movimenti_df[['data', 'cliente', 'tipo', 'prodotto', 'quantita', 'incasso', 'margine']],
                use_container_width=True,
                hide_index=True,
                height=300
            )
        else:
            st.info("Nessun movimento registrato nel ledger.")

# ------------------------------------------
# TAB 2: DASHBOARD & ANALYTICS
# ------------------------------------------
with tab2:
    st.subheader("📊 Dashboard & Analytics")
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

        if not movimenti_df.empty:
            mov_df = movimenti_df.copy()
            mov_df['Data_Ora'] = pd.to_datetime(mov_df['data'])
            mov_df = mov_df.sort_values('Data_Ora')
            mov_df['Incasso Totale'] = mov_df['incasso'].cumsum()
            mov_df['Margine Netto'] = mov_df['margine'].cumsum()
            
            chart_df = mov_df.melt(id_vars=['Data_Ora', 'prodotto', 'tipo'], value_vars=['Incasso Totale', 'Margine Netto'], var_name='Metrica', value_name='Valore (€)')
            chart = alt.Chart(chart_df).mark_line(point=True, strokeWidth=3).encode(
                x=alt.X('Data_Ora:T', title='Data e Ora'), y=alt.Y('Valore (€):Q', title='Importo (€)'),
                color=alt.Color('Metrica:N', scale=alt.Scale(domain=['Incasso Totale', 'Margine Netto'], range=['#f59e0b', '#38bdf8']))
            ).properties(height=350).interactive()
            st.altair_chart(chart, use_container_width=True)

# ------------------------------------------
# TAB 3: RIFORNIMENTI & FORNITORI (STILE HEIST BOARD GTA)
# ------------------------------------------
with tab3:
    st.subheader("🚚 Rifornimenti & Canali Clandestini")
    
    if st.session_state.offerta_fornitore:
        off = st.session_state.offerta_fornitore
        costo_tot = off['costo_totale']
        ha_abbastanza_soldi = st.session_state.soldi_cassa >= costo_tot

        st.markdown(f"""
        <div class="heist-board">
            <div class="heist-title">🎯 OBIETTIVO / CONTATTO: {off['fornitore_nome'].upper()}</div>
            <div class="heist-quote">{off['fornitore_frase']}</div>
            <div style="display: flex; justify-content: space-around; text-align: center; margin-top: 15px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 15px;">
                <div>
                    <span style="font-size: 0.70rem; color: #9ca3af; text-transform: uppercase; letter-spacing: 1px;">Merce</span><br>
                    <strong style="color: #f59e0b; font-size: 1.1rem; font-family: 'Anton', sans-serif;">{off['prodotto_nome']}</strong><br>
                    <span style="font-size: 0.65rem; color: #ef4444; font-weight: 700;">{off['tipo']}</span>
                </div>
                <div>
                    <span style="font-size: 0.70rem; color: #9ca3af; text-transform: uppercase; letter-spacing: 1px;">Quantità Lotto</span><br>
                    <strong style="color: #38bdf8; font-size: 1.1rem; font-family: 'Anton', sans-serif;">{off['quantita']:,.1f} g</strong>
                </div>
                <div>
                    <span style="font-size: 0.70rem; color: #9ca3af; text-transform: uppercase; letter-spacing: 1px;">Costo Unitario</span><br>
                    <strong style="color: #10b981; font-size: 1.1rem; font-family: 'Anton', sans-serif;">€ {off['costo_unitario']:.2f} / g</strong>
                </div>
            </div>
            <div style="text-align: center; margin-top: 18px; font-size: 1.25rem; font-family: 'Anton', sans-serif; color: #ffffff; letter-spacing: 1px;">
                INVESTIMENTO INTERO LOTTO: <span style="color: #f59e0b;">€ {costo_tot:,.2f}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
            
        if not ha_abbastanza_soldi:
            st.warning(f"⚠️ Fondi insufficienti in cassa (€{st.session_state.soldi_cassa:.2f}) per l'intero lotto da €{costo_tot:.2f}. Usa la trattativa per investire un budget ridotto.")

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("💼 COMPRA INTERO LOTTO (SUBITO)", use_container_width=True, disabled=not ha_abbastanza_soldi):
                st.session_state.soldi_cassa -= costo_tot
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT OR IGNORE INTO prodotti (nome, valore_mercato_unitario) VALUES (?, ?)", (off['prodotto_nome'], off['valore_mercato_suggerito']))
                    cursor.execute("SELECT id FROM prodotti WHERE nome = ?", (off['prodotto_nome'],))
                    p_id = cursor.fetchone()[0]

                    cursor.execute("""
                        INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (p_id, off['codice_lotto'], off['quantita'], off['quantita'], off['costo_unitario'], date.today(), date.today()))
                    l_id = cursor.lastrowid
                    cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, costo_totale, cliente, note) VALUES (?, ?, 'CARICO', ?, ?, ?, 'Acquisto Intero Lotto')", (p_id, l_id, off['quantita'], costo_tot, off['fornitore_nome']))

                aggiungi_log(f"🚚 ACQUISTO: Comprati {off['quantita']}g di {off['prodotto_nome']} da {off['fornitore_nome']} per €{costo_tot:.2f}")
                st.success(f"✅ Accordo chiuso con {off['fornitore_nome']}!")
                st.session_state.offerta_fornitore = None
                st.session_state.minigioco_trattativa = False
                st.rerun()

        with col_b2:
            if st.button("❌ BRUCIA CONTATTO E VATTENE", use_container_width=True):
                aggiungi_log(f"❌ Rifiutata offerta di {off['fornitore_nome']}.")
                st.info(f"Hai scartato il contatto di {off['fornitore_nome']}.")
                st.session_state.offerta_fornitore = None
                st.session_state.minigioco_trattativa = False
                st.rerun()

        st.markdown("---")
        with st.container(border=True):
            st.markdown("##### 📋 TRATTATIVA CLANDESTINA (OBIETTIVO BUDGET)")
            st.write("«Imposta quanti **soldi (€)** vuoi investire in questa trattativa: il fornitore calcolerà quanti grammi offrirti in base alla tua offerta e alle tue mosse tattiche.»")
            
            budget_proposto = st.number_input("Il tuo Budget da Spendere (€):", min_value=5.0, max_value=float(st.session_state.soldi_cassa), value=min(50.0, float(st.session_state.soldi_cassa)), step=5.0)
            
            approccio = st.selectbox("Approccio Negoziazione", [
                "🤝 Profilo Basso / Affidabile (Rischio minimo)", 
                "😎 Bluff Tattico (Tenta lo sconto aggressivo)", 
                "🔥 Pressing Totale (Alto rischio / Margine elevato)"
            ])
            
            if st.button("🎲 ESEGUI TRATTATIVA CON BUDGET", use_container_width=True):
                tiro = random.randint(1, 100) + int(st.session_state.reputazione / 2)
                
                if "Profilo Basso" in approccio:
                    sconto = 0.93 if tiro > 35 else 1.08
                    esito_txt = "Il contatto apprezza la tua affidabilità."
                elif "Bluff" in approccio:
                    sconto = 0.82 if tiro > 60 else 1.25
                    esito_txt = "Hai giocato d'azzardo sulla tua reputazione."
                else:
                    sconto = 0.70 if tiro > 82 else 1.40
                    esito_txt = "Mossa ad altissimo rischio nel vicolo buio!"
                    
                nuovo_costo_u = round(off['costo_unitario'] * sconto, 2)
                qta_calcolata = round(budget_proposto / nuovo_costo_u, 2) if nuovo_costo_u > 0 else 0.0
                
                if qta_calcolata > off['quantita']:
                    qta_calcolata = float(off['quantita'])
                    budget_proposto = round(qta_calcolata * nuovo_costo_u, 2)

                st.session_state.minigioco_risultato = {
                    "budget": budget_proposto,
                    "costo_u": nuovo_costo_u,
                    "qta_offerta": qta_calcolata,
                    "testo_esito": esito_txt
                }
                st.rerun()

            if 'minigioco_risultato' in st.session_state and st.session_state.minigioco_risultato:
                res = st.session_state.minigioco_risultato
                st.info(f"💬 **Esito:** _{res['testo_esito']}_ -> Con il tuo budget di **€{res['budget']:.2f}** ti propongono **{res['qta_offerta']:.1f}g** (a €{res['costo_u']:.2f}/g).")
                
                ha_soldi_trattativa = st.session_state.soldi_cassa >= res['budget']
                if st.button("✅ CONFERMA ACCORDO E RITIRA MERCE", use_container_width=True, disabled=not ha_soldi_trattativa):
                    st.session_state.soldi_cassa -= res['budget']
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("INSERT OR IGNORE INTO prodotti (nome, valore_mercato_unitario) VALUES (?, ?)", (off['prodotto_nome'], off['valore_mercato_suggerito']))
                        cursor.execute("SELECT id FROM prodotti WHERE nome = ?", (off['prodotto_nome'],))
                        p_id = cursor.fetchone()[0]

                        cursor.execute("""
                            INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (p_id, f"{off['codice_lotto']}-BUDGET", res['qta_offerta'], res['qta_offerta'], res['costo_u'], date.today(), date.today()))
                        l_id = cursor.lastrowid
                        cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, costo_totale, cliente, note) VALUES (?, ?, 'CARICO', ?, ?, ?, 'Acquisto con Budget')", (p_id, l_id, res['qta_offerta'], res['budget'], off['fornitore_nome']))

                    aggiungi_log(f"🚚 ACQUISTO BUDGET: Presi {res['qta_offerta']}g di {off['prodotto_nome']} da {off['fornitore_nome']} per €{res['budget']:.2f}")
                    st.success("✅ Accordo chiuso con successo!")
                    st.session_state.offerta_fornitore = None
                    st.session_state.minigioco_risultato = None
                    st.rerun()

    else:
        fornitori_rimasti = st.session_state.max_fornitori_oggi - st.session_state.fornitori_visti_oggi
        if fornitori_rimasti > 0:
            st.info(f"Oggi puoi ancora intercettare fino a {fornitori_rimasti} contatto/i clandestino/i.")
            if st.button("📞 Sintonizzati su Canale Clandestino", use_container_width=True):
                genera_offerta_fornitore_casuale()
                st.rerun()
        else:
            st.warning("⚠️ Nessun contatto disponibile oggi sui canali sotterranei. Riposa per avanzare.")

    st.markdown("---")
    st.markdown("### 📋 Stato Lotti e Scorte Attuali")
    soglia_attuale = get_soglia_esaurimento()
    report_lotti_df = get_report_lotti_integrato_df(soglia_esaurimento_g=soglia_attuale)
    
    if not report_lotti_df.empty:
        st.dataframe(report_lotti_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    with st.expander("➕ Inserimento Manuale Lotto (Emergenza)"):
        with st.form("form_nuovo_prodotto_lotto"):
            nome_nuovo = st.text_input("Nome Prodotto")
            data_acq_m = st.date_input("Data Acquisto", value=date.today())
            cod_lotto_m = st.text_input("Codice Lotto", value=genera_codice_lotto_automatico(data_acq_m))
            qta_lotto_m = st.number_input("Quantità (g)", value=25.0)
            costo_u_lotto_m = st.number_input("Costo d'Acquisto (€/g)", value=4.0)
            prezzo_v_init = st.number_input("Prezzo Vendita (€/g)", value=9.0)

            if st.form_submit_button("Crea Prodotto e Registra Lotto"):
                costo_t_m = qta_lotto_m * costo_u_lotto_m
                if st.session_state.soldi_cassa < costo_t_m:
                    st.error("Fondi insufficienti in cassa!")
                else:
                    st.session_state.soldi_cassa -= costo_t_m
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO prodotti (nome, valore_mercato_unitario) VALUES (?, ?)", (nome_nuovo.strip(), prezzo_v_init))
                        p_id = cursor.lastrowid
                        cursor.execute("INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico) VALUES (?, ?, ?, ?, ?, ?, ?)", (p_id, cod_lotto_m.strip(), qta_lotto_m, qta_lotto_m, costo_u_lotto_m, data_acq_m, date.today()))
                        lotto_id = cursor.lastrowid
                        cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, costo_totale, cliente) VALUES (?, ?, 'CARICO', ?, ?, 'Fornitore Manuale')", (p_id, lotto_id, qta_lotto_m, costo_t_m))
                    st.success("✅ Prodotto e lotto registrati!")
                    st.rerun()

# ------------------------------------------
# TAB 4: STATISTICHE CLIENTI & DEBITI
# ------------------------------------------
with tab4:
    st.subheader("📈 Statistiche Avanzate Clienti")
    movimenti_df = get_movimenti_dettagliati_df()
    
    if not movimenti_df.empty:
        clienti_debito = movimenti_df[(movimenti_df['tipo'] == 'VENDITA') & (movimenti_df['stato_pagamento'] == 'Dopo (Credito)')]
        if not clienti_debito.empty:
            debito_per_cliente = clienti_debito.groupby('cliente')['incasso'].sum().reset_index()
            st.markdown("##### 💳 Clienti con Debiti Attivi")
            for _, r_d in debito_per_cliente.iterrows():
                col_d1, col_d2 = st.columns([3, 1])
                col_d1.write(f"**{r_d['cliente']}**: € {r_d['incasso']:,.2f}")
                if col_d2.button(f"Salda Debito", key=f"btn_s_{r_d['cliente']}"):
                    segna_debito_pagato(r_d['cliente'])
                    st.success("Debito saldato e incassato in cassa!")
                    st.rerun()

# ------------------------------------------
# TAB 5: REPORT STORICO & RESET GAME
# ------------------------------------------
with tab5:
    st.subheader("📜 Registro Storico Transazioni")
    movimenti_df = get_movimenti_dettagliati_df()
    if not movimenti_df.empty:
        st.dataframe(movimenti_df, use_container_width=True, hide_index=True)
        csv_data = movimenti_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Scarica Report CSV", data=csv_data, file_name="report_storico.csv", mime="text/csv")
    
    st.markdown("---")
    
    with st.expander("⚠️ DANGER ZONE: Resetta Dati e Inizia Nuova Partita", expanded=False):
        st.error("Questa operazione cancellerà permanentemente tutto lo storico vendite, i clienti, i lotti e azzererà la tua partita riportandoti al Giorno 1 con €200.")
        conferma_reset = st.checkbox("Sono sicuro di voler piallare tutti i dati e ricominciare da capo.")
        
        if st.button("💥 RESETTA TUTTO E RICOMINCIA DA ZERO", use_container_width=True):
            if conferma_reset:
                reset_completo_nuova_partita()
                st.success("🎉 Reset eseguito! Benvenuto nella tua nuova partita.")
                st.rerun()
            else:
                st.warning("Spunta la casella di conferma qui sopra per poter procedere col reset.")