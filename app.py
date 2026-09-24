import sqlite3
from datetime import datetime, date
import pandas as pd
import streamlit as st

# ==========================================
# CONFIGURAZIONE PAGINA STREAMLIT
# ==========================================
st.set_page_config(
    page_title="Labzz",
    page_icon="📦",
    layout="wide"
)

DB_NAME = "magazzino.db"

# ==========================================
# GESTIONE DATABASE SQLITE (CONTEXT MANAGER)
# ==========================================
def get_connection():
    return sqlite3.connect(DB_NAME, timeout=10)

def init_db():
    """Inizializza il database SQLite verificando e creando tabelle/colonne."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Anagrafica prodotti con colonna scorta_minima_g
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS prodotti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            unita_misura TEXT DEFAULT 'g',
            valore_mercato_unitario REAL DEFAULT 0,
            scorta_minima_g REAL DEFAULT 0
        )
        """)
        
        # Migrazione schema: Aggiunge scorta_minima_g se il DB esisteva già senza
        cursor.execute("PRAGMA table_info(prodotti)")
        colonne = [column[1] for column in cursor.fetchall()]
        if 'scorta_minima_g' not in colonne:
            cursor.execute("ALTER TABLE prodotti ADD COLUMN scorta_minima_g REAL DEFAULT 0")

        # 2. Registro lotti di carico
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS lotti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prodotto_id INTEGER NOT NULL,
            codice_lotto TEXT NOT NULL,
            quantita_iniziale REAL NOT NULL,
            quantita_attuale REAL NOT NULL,
            costo_acquisto_unitario REAL NOT NULL,
            data_carico DATE NOT NULL,
            data_scadenza DATE,
            FOREIGN KEY (prodotto_id) REFERENCES prodotti (id)
        )
        """)
        
        # 3. Registro movimenti (carico, vendita, XME)
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
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prodotto_id) REFERENCES prodotti (id),
            FOREIGN KEY (lotto_id) REFERENCES lotti (id)
        )
        """)
        
        # Inserisci prodotti base se la tabella è vuota
        cursor.execute("SELECT COUNT(*) FROM prodotti")
        if cursor.fetchone()[0] == 0:
            prodotti_iniziali = [
                ("Farina", "g", 1.0, 500.0),
                ("Zucchero", "g", 1.0, 500.0),
                ("Cioccolata", "g", 2.5, 200.0),
                ("Fieno", "g", 0.5, 1000.0)
            ]
            cursor.executemany("""
                INSERT INTO prodotti (nome, unita_misura, valore_mercato_unitario, scorta_minima_g)
                VALUES (?, ?, ?, ?)
            """, prodotti_iniziali)

# Inizializzazione iniziale
init_db()

# ==========================================
# FUNZIONI UTILITY DATI
# ==========================================
def get_prodotti_df():
    with get_connection() as conn:
        return pd.read_sql_query("SELECT * FROM prodotti", conn)

def get_lotti_df():
    query = """
        SELECT l.id, p.nome AS prodotto, l.codice_lotto, l.quantita_attuale, 
               'g' AS unita_misura, l.costo_acquisto_unitario, l.data_carico, l.data_scadenza
        FROM lotti l
        JOIN prodotti p ON l.prodotto_id = p.id
        WHERE l.quantita_attuale > 0
        ORDER BY l.data_scadenza ASC
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)

def get_movimenti_df():
    query = """
        SELECT m.id, m.data, p.nome AS prodotto, m.tipo, m.quantita, 'g' AS unita_misura,
               m.prezzo_unitario, m.ricavo_totale, m.costo_totale, m.margine, m.note, m.lotto_id
        FROM movimenti m
        JOIN prodotti p ON m.prodotto_id = p.id
        ORDER BY m.data DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)

def calcola_stato_magazzino():
    with get_connection() as conn:
        prodotti_df = pd.read_sql_query("SELECT * FROM prodotti", conn)
        lotti_df = pd.read_sql_query("SELECT * FROM lotti WHERE quantita_attuale > 0", conn)
        movimenti_df = pd.read_sql_query("SELECT * FROM movimenti", conn)

    risultati = []
    
    for _, prod in prodotti_df.iterrows():
        p_id = prod['id']
        lotti_prod = lotti_df[lotti_df['prodotto_id'] == p_id]
        
        qta_totale = float(lotti_prod['quantita_attuale'].sum())
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

def storna_movimento(movimento_id):
    """Gestisce l'annullamento/storno sicuro di un singolo movimento."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM movimenti WHERE id = ?", (movimento_id,))
        mov = cursor.fetchone()
        
        if not mov:
            return False, "Movimento non trovato."
        
        # Struttura tuple movimenti: 0:id, 1:prodotto_id, 2:lotto_id, 3:tipo, 4:quantita, 5:prezzo_unitario, ...
        p_id, lotto_id, tipo, qta = mov[1], mov[2], mov[3], float(mov[4])
        
        if tipo in ['VENDITA', 'XME']:
            # Ripristina la quantità nel lotto originale o in quello più recente
            if lotto_id:
                cursor.execute("UPDATE lotti SET quantita_attuale = quantita_attuale + ? WHERE id = ?", (qta, lotto_id))
            else:
                cursor.execute("""
                    UPDATE lotti SET quantita_attuale = quantita_attuale + ? 
                    WHERE id = (SELECT id FROM lotti WHERE prodotto_id = ? ORDER BY id DESC LIMIT 1)
                """, (qta, p_id))
        elif tipo == 'CARICO':
            # Se è un acquisto, riduci la quantità del lotto creato
            if lotto_id:
                cursor.execute("UPDATE lotti SET quantita_attuale = MAX(0, quantita_attuale - ?) WHERE id = ?", (qta, lotto_id))
        
        # Rimuovi il movimento dal registro
        cursor.execute("DELETE FROM movimenti WHERE id = ?", (movimento_id,))
        return True, "Movimento stornato con successo!"

# ==========================================
# INTERFACCIA UTENTE (STREAMLIT)
# ==========================================
st.title("📦 Labzz")

# Tabs principali
tab1, tab2, tab3, tab4 = st.tabs([
    "💸 Cassa & Movimenti", 
    "📋 Gestione Stock", 
    "📊 Dashboard & KPI", 
    "📜 Report & Storico"
])

# ------------------------------------------
# TAB 1: CASSA & REGISTRA MOVIMENTI
# ------------------------------------------
with tab1:
    st.subheader("Cassa Operativa")
    
    tipo_operazione = st.radio("Seleziona Operazione", ["Vendita", "Acquisto", "XME"], horizontal=True)
    prodotti_df = get_prodotti_df()
    
    if prodotti_df.empty:
        st.warning("Nessun prodotto presente in anagrafica. Aggiungi un prodotto dalla scheda 'Gestione Stock'.")
    else:
        if tipo_operazione == "Vendita":
            prod_nome = st.selectbox("Seleziona Prodotto da Vendere", prodotti_df['nome'].tolist())
            prod_row = prodotti_df[prodotti_df['nome'] == prod_nome].iloc[0]
            p_id = int(prod_row['id'])
            
            with get_connection() as conn:
                query_lotti = "SELECT * FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0 ORDER BY data_scadenza ASC"
                lotti_disponibili = pd.read_sql_query(query_lotti, conn, params=(p_id,))

            if lotti_disponibili.empty:
                st.error(f"⚠️ Nessuna disponibilità in magazzino per **{prod_nome}**.")
            else:
                qta_tot_disp = float(lotti_disponibili['quantita_attuale'].sum())
                st.info(f"Disponibilità attuale per **{prod_nome}**: **{qta_tot_disp:,.1f} g**")
                
                with st.form("form_vendita"):
                    st.markdown("##### Registra Vendita")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        quantita_vendita = st.number_input("Quantità da Vendere (g)", min_value=0.5, value=100.0, step=0.5, format="%.1f")
                        prezzo_vendita_unitario = st.number_input("Prezzo al grammo (€/g)", min_value=0.1, value=float(prod_row['valore_mercato_unitario']), step=0.5, format="%.2f")
                    
                    with col2:
                        totale_vendita = quantita_vendita * prezzo_vendita_unitario
                        st.metric("Totale Incasso Previsto", f"€ {totale_vendita:,.2f}")
                        note = st.text_input("Note (Opzionale)")

                    if st.form_submit_button("Vendita"):
                        if quantita_vendita > qta_tot_disp:
                            st.error(f"Quantità inserita ({quantita_vendita:,.1f} g) superiore alla disponibilità ({qta_tot_disp:,.1f} g).")
                        else:
                            with get_connection() as conn:
                                cursor = conn.cursor()
                                qta_rimanente = float(quantita_vendita)
                                costo_totale_acquisto = 0.0
                                
                                for _, lotto in lotti_disponibili.iterrows():
                                    if qta_rimanente <= 0:
                                        break
                                    
                                    l_id = int(lotto['id'])
                                    qta_lotto = float(lotto['quantita_attuale'])
                                    costo_u = float(lotto['costo_acquisto_unitario'])
                                    
                                    if qta_lotto <= qta_rimanente:
                                        prelievo = qta_lotto
                                        qta_rimanente -= qta_lotto
                                        nuova_qta = 0.0
                                    else:
                                        prelievo = qta_rimanente
                                        nuova_qta = qta_lotto - qta_rimanente
                                        qta_rimanente = 0.0
                                    
                                    costo_totale_acquisto += prelievo * costo_u
                                    cursor.execute("UPDATE lotti SET quantita_attuale = ? WHERE id = ?", (nuova_qta, l_id))
                                
                                ricavo_totale = quantita_vendita * prezzo_vendita_unitario
                                margine = ricavo_totale - costo_totale_acquisto
                                
                                cursor.execute("""
                                    INSERT INTO movimenti (prodotto_id, tipo, quantita, prezzo_unitario, ricavo_totale, costo_totale, margine, note)
                                    VALUES (?, 'VENDITA', ?, ?, ?, ?, ?, ?)
                                """, (p_id, quantita_vendita, prezzo_vendita_unitario, ricavo_totale, costo_totale_acquisto, margine, note))
                            
                            st.success(f"✅ Vendita registrata! Incasso: € {ricavo_totale:,.2f} | Margine: € {margine:,.2f}")
                            st.rerun()

        elif tipo_operazione == "Acquisto":
            with st.form("form_carico"):
                st.markdown("##### Registra Acquisto Stock")
                col1, col2 = st.columns(2)
                
                with col1:
                    prod_nome = st.selectbox("Prodotto", prodotti_df['nome'].tolist())
                    quantita = st.number_input("Quantità Acquistata (g)", min_value=0.5, value=1000.0, step=0.5, format="%.1f")
                    costo_unitario = st.number_input("Costo d'Acquisto al grammo (€/g)", min_value=0.1, value=1.0, step=0.5, format="%.2f")
                    
                with col2:
                    codice_lotto = st.text_input("Codice Lotto", value=f"LOTTO-{datetime.now().strftime('%Y%m%d-%H%M')}")
                    data_scadenza = st.date_input("Data di Scadenza", value=date.today())
                    note = st.text_input("Note Aggiuntive")

                if st.form_submit_button("Acquisto"):
                    prod_row = prodotti_df[prodotti_df['nome'] == prod_nome].iloc[0]
                    p_id = int(prod_row['id'])
                    
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_carico, data_scadenza)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (p_id, codice_lotto, quantita, quantita, costo_unitario, date.today(), data_scadenza))
                        
                        lotto_id = cursor.lastrowid
                        costo_totale = quantita * costo_unitario
                        
                        cursor.execute("""
                            INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, costo_totale, note)
                            VALUES (?, ?, 'CARICO', ?, ?, ?, ?)
                        """, (p_id, lotto_id, quantita, costo_unitario, costo_totale, note))
                    
                    st.success(f"✅ Acquisto registrato col lotto {codice_lotto}!")
                    st.rerun()

        elif tipo_operazione == "XME":
            lotti_df = get_lotti_df()
            
            if lotti_df.empty:
                st.error("Nessun lotto disponibile per l'operazione XME.")
            else:
                with st.form("form_xme"):
                    st.markdown("##### Registra XME")
                    
                    opzioni_lotto = {f"{r['prodotto']} - Lotto: {r['codice_lotto']} (Disp: {r['quantita_attuale']:,.1f} g)": r['id'] for _, r in lotti_df.iterrows()}
                    lotto_selezionato_label = st.selectbox("Seleziona Lotto", list(opzioni_lotto.keys()))
                    lotto_id_scelto = opzioni_lotto[lotto_selezionato_label]
                    
                    lotto_row = lotti_df[lotti_df['id'] == lotto_id_scelto].iloc[0]
                    
                    qta_xme = st.number_input("Quantità (g)", min_value=0.5, max_value=float(lotto_row['quantita_attuale']), value=10.0, step=0.5, format="%.1f")
                    motivo = st.text_input("Note XME", placeholder="Es. Utilizzo personale, Note varie")

                    if st.form_submit_button("Conferma XME"):
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            nuova_qta = float(lotto_row['quantita_attuale']) - qta_xme
                            costo_perdita = qta_xme * float(lotto_row['costo_acquisto_unitario'])
                            
                            p_id = int(prodotti_df[prodotti_df['nome'] == lotto_row['prodotto']].iloc[0]['id'])
                            
                            cursor.execute("UPDATE lotti SET quantita_attuale = ? WHERE id = ?", (nuova_qta, lotto_id_scelto))
                            cursor.execute("""
                                INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, costo_totale, margine, note)
                                VALUES (?, ?, 'XME', ?, 0, ?, ?, ?)
                            """, (p_id, lotto_id_scelto, qta_xme, costo_perdita, -costo_perdita, f"XME: {motivo}"))
                        
                        st.warning(f"Operazione XME registrata! Valore associato: € {costo_perdita:,.2f}")
                        st.rerun()

# ------------------------------------------
# TAB 2: GESTIONE STOCK & AGGIUNTA RAPIDA
# ------------------------------------------
with tab2:
    st.subheader("📋 Gestione dello Stock (Unità: Grammi - g)")
    
    # AVVISI SCORTA MINIMA
    df_stato = calcola_stato_magazzino()
    sotto_scorta = df_stato[df_stato['qta_disponibile'] < df_stato['scorta_minima_g']]
    if not sotto_scorta.empty:
        for _, r in sotto_scorta.iterrows():
            st.warning(f"⚠️ **Sotto scorta minima!** {r['prodotto']}: attuale {r['qta_disponibile']:,.1f} g (Soglia minima: {r['scorta_minima_g']:,.1f} g)")

    col_a, col_b = st.columns(2)
    
    with col_a:
        with st.expander("➕ **Aggiungi Nuovo Prodotto**", expanded=False):
            with st.form("form_nuovo_prodotto"):
                nome_nuovo = st.text_input("Nome Prodotto", placeholder="Es. Zafferano, Spezia")
                qta_iniziale = st.number_input("Quantità Iniziale (g)", min_value=0.0, value=1000.0, step=0.5, format="%.1f")
                costo_u_init = st.number_input("Costo d'Acquisto al grammo (€/g)", min_value=0.1, value=1.0, step=0.5, format="%.2f")
                prezzo_v_init = st.number_input("Prezzo di Vendita al grammo (€/g)", min_value=0.1, value=2.0, step=0.5, format="%.2f")
                scorta_min_init = st.number_input("Scorta Minima Alert (g)", min_value=0.0, value=100.0, step=10.0, format="%.1f")

                if st.form_submit_button("Crea Prodotto"):
                    if nome_nuovo.strip() == "":
                        st.error("Inserisci un nome valido.")
                    else:
                        try:
                            with get_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute("""
                                    INSERT INTO prodotti (nome, unita_misura, valore_mercato_unitario, scorta_minima_g) 
                                    VALUES (?, 'g', ?, ?)
                                """, (nome_nuovo.strip(), prezzo_v_init, scorta_min_init))
                                p_id = cursor.lastrowid
                                
                                if qta_iniziale > 0:
                                    codice_lotto = f"LOTTO-INIT-{datetime.now().strftime('%Y%m%d')}"
                                    cursor.execute("""
                                        INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_carico, data_scadenza)
                                        VALUES (?, ?, ?, ?, ?, ?, ?)
                                    """, (p_id, codice_lotto, qta_iniziale, qta_iniziale, costo_u_init, date.today(), date.today()))
                                    
                                    lotto_id = cursor.lastrowid
                                    cursor.execute("""
                                        INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, costo_totale, note)
                                        VALUES (?, ?, 'CARICO', ?, ?, ?, 'Inizializzazione Prodotto')
                                    """, (p_id, lotto_id, qta_iniziale, costo_u_init, qta_iniziale * costo_u_init))
                                    
                            st.success(f"Prodotto '{nome_nuovo}' salvato con successo!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Un prodotto con questo nome esiste già.")

    with col_b:
        with st.expander("⚡ **Aggiorna Prodotto Esistente / Scorta Minima**", expanded=True):
            prodotti_df = get_prodotti_df()
            if not prodotti_df.empty:
                prod_mod_nome = st.selectbox("Seleziona Prodotto da Modificare", prodotti_df['nome'].tolist())
                p_row = prodotti_df[prodotti_df['nome'] == prod_mod_nome].iloc[0]
                p_id = int(p_row['id'])
                
                with get_connection() as conn:
                    lotti_p = pd.read_sql_query("SELECT * FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0", conn, params=(p_id,))
                
                qta_attuale_tot = float(lotti_p['quantita_attuale'].sum()) if not lotti_p.empty else 0.0
                costo_u_att = float((lotti_p['quantita_attuale'] * lotti_p['costo_acquisto_unitario']).sum() / qta_attuale_tot) if qta_attuale_tot > 0 else 1.0

                with st.form("form_rettifica_diretta"):
                    nuova_qta_tot = st.number_input("Nuova Quantità Totale (g)", min_value=0.0, value=qta_attuale_tot, step=0.5, format="%.1f")
                    nuovo_costo_grammo = st.number_input("Costo d'Acquisto Unitario (€/g)", min_value=0.1, value=float(costo_u_att if costo_u_att > 0 else 1.0), step=0.5, format="%.2f")
                    nuovo_prezzo_grammo = st.number_input("Prezzo di Vendita Unitario (€/g)", min_value=0.1, value=float(p_row['valore_mercato_unitario']), step=0.5, format="%.2f")
                    nuova_scorta_min_g = st.number_input("Soglia Scorta Minima (g)", min_value=0.0, value=float(p_row['scorta_minima_g']), step=10.0, format="%.1f")

                    if st.form_submit_button("Salva Modifiche"):
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE prodotti 
                                SET valore_mercato_unitario = ?, scorta_minima_g = ? 
                                WHERE id = ?
                            """, (nuovo_prezzo_grammo, nuova_scorta_min_g, p_id))
                            
                            cursor.execute("UPDATE lotti SET quantita_attuale = 0 WHERE prodotto_id = ?", (p_id,))
                            
                            if nuova_qta_tot > 0:
                                cod_lotto_rett = f"RETT-{datetime.now().strftime('%Y%m%d-%H%M')}"
                                cursor.execute("""
                                    INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_carico)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                """, (p_id, cod_lotto_rett, nuova_qta_tot, nuova_qta_tot, nuovo_costo_grammo, date.today()))
                        
                        st.success(f"Stock e parametri di '{prod_mod_nome}' aggiornati!")
                        st.rerun()

    st.markdown("---")
    
    st.subheader("Giacenza Attuale")
    st.dataframe(
        df_stato[[
            'prodotto', 'qta_disponibile', 'scorta_minima_g', 'unita_misura',
            'costo_medio_ponderato', 'valore_mercato_unitario',
            'valore_totale_costo', 'valore_totale_mercato'
        ]],
        column_config={
            "prodotto": "Prodotto",
            "qta_disponibile": st.column_config.NumberColumn("Quantità Disponibile", format="%.1f g"),
            "scorta_minima_g": st.column_config.NumberColumn("Scorta Minima", format="%.1f g"),
            "unita_misura": "U.M.",
            "costo_medio_ponderato": st.column_config.NumberColumn("Costo Medio", format="€ %.2f"),
            "valore_mercato_unitario": st.column_config.NumberColumn("Prezzo Vendita", format="€ %.2f"),
            "valore_totale_costo": st.column_config.NumberColumn("Valore Costo Totale", format="€ %.2f"),
            "valore_totale_mercato": st.column_config.NumberColumn("Valore Vendita Totale", format="€ %.2f")
        },
        use_container_width=True,
        hide_index=True
    )

# ------------------------------------------
# TAB 3: DASHBOARD & KPI
# ------------------------------------------
with tab3:
    st.subheader("Dashboard & Analytics")
    df_stato = calcola_stato_magazzino()
    lotti_df = get_lotti_df()

    # Avviso Scorta Minima
    sotto_scorta_dash = df_stato[df_stato['qta_disponibile'] < df_stato['scorta_minima_g']]
    if not sotto_scorta_dash.empty:
        for _, r in sotto_scorta_dash.iterrows():
            st.warning(f"⚠️ **Sotto scorta minima!** {r['prodotto']}: attuale {r['qta_disponibile']:,.1f} g (Scorta Minima: {r['scorta_minima_g']:,.1f} g)")

    # Avviso Scadenze
    if not lotti_df.empty:
        lotti_df['data_scadenza'] = pd.to_datetime(lotti_df['data_scadenza'])
        oggi = pd.to_datetime(date.today())
        lotti_in_scadenza = lotti_df[(lotti_df['data_scadenza'] - oggi).dt.days <= 15]
        
        if not lotti_in_scadenza.empty:
            for _, row in lotti_in_scadenza.iterrows():
                giorni = (row['data_scadenza'] - oggi).days
                msg = f"In scadenza tra {giorni} giorni!" if giorni >= 0 else "SCADUTO!"
                st.error(f"🚨 **Lotto {row['codice_lotto']} ({row['prodotto']})**: {msg} (Data: {row['data_scadenza'].strftime('%Y-%m-%d')})")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Valore Magazzino (Costo)", f"€ {df_stato['valore_totale_costo'].sum():,.2f}")
    col2.metric("Valore Magazzino (Vendita)", f"€ {df_stato['valore_totale_mercato'].sum():,.2f}")
    col3.metric("Incasso Totale Vendite", f"€ {df_stato['incasso_totale'].sum():,.2f}")
    col4.metric("Margine Netto Effettivo", f"€ {df_stato['margine_totale'].sum():,.2f}")

    st.markdown("---")

    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        st.subheader("Valore Stock per Prodotto (€)")
        chart_data_valore = df_stato.set_index('prodotto')[['valore_totale_costo', 'valore_totale_mercato']]
        chart_data_valore.columns = ['Costo Totale', 'Mercato Totale']
        st.bar_chart(chart_data_valore)

    with col_g2:
        st.subheader("Vendite e Margini (€)")
        chart_data_vendite = df_stato.set_index('prodotto')[['incasso_totale', 'margine_totale']]
        chart_data_vendite.columns = ['Incasso', 'Margine']
        st.bar_chart(chart_data_vendite)

# ------------------------------------------
# TAB 4: REPORT & STORICO
# ------------------------------------------
with tab4:
    st.subheader("Registro Storico Transazioni")
    
    movimenti_df = get_movimenti_df()
    
    if movimenti_df.empty:
        st.info("Nessuna transazione registrata nel database.")
    else:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            prod_filtro = st.multiselect("Filtra per Prodotto", options=movimenti_df['prodotto'].unique(), default=movimenti_df['prodotto'].unique())
        with col_f2:
            tipo_filtro = st.multiselect("Filtra per Tipo Operazione", options=movimenti_df['tipo'].unique(), default=movimenti_df['tipo'].unique())
            
        df_filtrato = movimenti_df[
            (movimenti_df['prodotto'].isin(prod_filtro)) & 
            (movimenti_df['tipo'].isin(tipo_filtro))
        ].copy()

        st.dataframe(
            df_filtrato[[
                'id', 'data', 'prodotto', 'tipo', 'quantita', 'unita_misura',
                'prezzo_unitario', 'ricavo_totale', 'costo_totale', 'margine', 'note'
            ]],
            column_config={
                "id": "ID",
                "data": "Data/Ora",
                "prodotto": "Prodotto",
                "tipo": "Tipo Operazione",
                "quantita": st.column_config.NumberColumn("Quantità", format="%.1f g"),
                "unita_misura": "U.M.",
                "prezzo_unitario": st.column_config.NumberColumn("Prezzo Unit.", format="€ %.2f"),
                "ricavo_totale": st.column_config.NumberColumn("Ricavo", format="€ %.2f"),
                "costo_totale": st.column_config.NumberColumn("Costo", format="€ %.2f"),
                "margine": st.column_config.NumberColumn("Margine", format="€ %.2f"),
                "note": "Note"
            },
            use_container_width=True,
            hide_index=True
        )

        csv_data = df_filtrato.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Scarica Storico in CSV",
            data=csv_data,
            file_name=f"storico_magazzino_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

        st.markdown("---")
        
        # ANNULLAMENTO / STORNO SINGOLO MOVIMENTO
        st.subheader("🔄 Storno e Annullamento Singolo Movimento")
        with st.expander("🛠️ **Annulla una transazione specifica per errore**"):
            st.write("Seleziona l'ID della transazione da stornare. La quantità verrà ripristinata nel relativo lotto.")
            
            # Mappatura per il selectbox
            opzioni_movimenti = {
                f"ID {r['id']} | {r['data']} | {r['prodotto']} | {r['tipo']} ({r['quantita']} g)": r['id']
                for _, r in df_filtrato.iterrows()
            }
            
            mov_selezionato_label = st.selectbox("Seleziona Transazione da Annullare", list(opzioni_movimenti.keys()))
            id_mov_da_stornare = opzioni_movimenti[mov_selezionato_label]
            
            if st.button("❌ Storna / Annulla Questa Transazione"):
                success, msg = storna_movimento(id_mov_da_stornare)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    st.markdown("---")
    
    # SEZIONE DI RESET TOTALE DEI REPORT
    st.subheader("⚙️ Reset Globale Report")
    with st.expander("🚨 **Pulsante di Reset Totale Storico**"):
        st.warning("Attenzione: l'operazione cancellerà definitivamente TUTTE le transazioni storiche registrate.")
        
        if "conferma_reset" not in st.session_state:
            st.session_state["conferma_reset"] = False

        if not st.session_state["conferma_reset"]:
            if st.button("🗑️ Resetta Tutto lo Storico Transazioni"):
                st.session_state["conferma_reset"] = True
                st.rerun()
        else:
            st.error("Sei davvero sicuro di voler cancellare TUTTE le transazioni?")
            col_res1, col_res2 = st.columns(2)
            with col_res1:
                if st.button("✅ Sì, Cancella Definitivamente"):
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM movimenti")
                    st.session_state["conferma_reset"] = False
                    st.success("Storico delle transazioni resettato con successo!")
                    st.rerun()
            with col_res2:
                if st.button("❌ Annulla"):
                    st.session_state["conferma_reset"] = False
                    st.rerun()