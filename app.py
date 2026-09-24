import sqlite3
from datetime import datetime, date
import pandas as pd
import streamlit as st
import altair as alt

# ==========================================
# CONFIGURAZIONE PAGINA STREAMLIT
# ==========================================
st.set_page_config(
    page_title="Labzz - Gestione Magazzino FIFO",
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
        
        # 1. Anagrafica prodotti
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS prodotti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            unita_misura TEXT DEFAULT 'g',
            valore_mercato_unitario REAL DEFAULT 0,
            scorta_minima_g REAL DEFAULT 0
        )
        """)
        
        # Migrazione schema per scorta_minima_g
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

init_db()

# ==========================================
# FUNZIONI UTILITY DATI
# ==========================================
def get_prodotti_df():
    with get_connection() as conn:
        return pd.read_sql_query("SELECT * FROM prodotti ORDER BY nome ASC", conn)

def get_prodotti_disponibili_df():
    query = """
        SELECT DISTINCT p.* 
        FROM prodotti p
        JOIN lotti l ON p.id = l.prodotto_id
        WHERE l.quantita_attuale > 0
        ORDER BY p.nome ASC
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)

def get_lotti_attivi_df():
    query = """
        SELECT l.id, p.nome AS prodotto, l.codice_lotto, l.quantita_iniziale, l.quantita_attuale, 
               'g' AS unita_misura, l.costo_acquisto_unitario, l.data_carico, l.data_scadenza
        FROM lotti l
        JOIN prodotti p ON l.prodotto_id = p.id
        WHERE l.quantita_attuale > 0
        ORDER BY l.data_scadenza ASC, l.id ASC
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)

def get_storico_lotti_df():
    query = """
        SELECT l.id AS lotto_id, p.nome AS prodotto, l.codice_lotto, l.quantita_iniziale, l.quantita_attuale,
               'g' AS unita_misura, l.costo_acquisto_unitario, l.data_carico, l.data_scadenza,
               (l.quantita_iniziale * l.costo_acquisto_unitario) AS costo_totale_sostenuto,
               COALESCE(SUM(CASE WHEN m.tipo = 'VENDITA' THEN m.ricavo_totale ELSE 0 END), 0) AS incasso_generato,
               COALESCE(SUM(CASE WHEN m.tipo = 'VENDITA' THEN m.margine ELSE 0 END), 0) - 
               COALESCE(SUM(CASE WHEN m.tipo = 'XME' THEN m.costo_totale ELSE 0 END), 0) AS guadagno_netto_lotto
        FROM lotti l
        JOIN prodotti p ON l.prodotto_id = p.id
        LEFT JOIN movimenti m ON l.id = m.lotto_id
        GROUP BY l.id
        ORDER BY l.data_carico DESC, l.id DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)

def get_movimenti_df():
    query = """
        SELECT m.id, m.data, p.nome AS prodotto, m.tipo, m.quantita, 'g' AS unita_misura,
               m.prezzo_unitario, m.ricavo_totale, m.costo_totale, m.margine, m.note, m.lotto_id, l.codice_lotto
        FROM movimenti m
        JOIN prodotti p ON m.prodotto_id = p.id
        LEFT JOIN lotti l ON m.lotto_id = l.id
        ORDER BY m.data ASC
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)

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

def storna_movimento(movimento_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM movimenti WHERE id = ?", (movimento_id,))
        mov = cursor.fetchone()
        
        if not mov:
            return False, "Movimento non trovato."
        
        p_id, lotto_id, tipo, qta = mov[1], mov[2], mov[3], float(mov[4])
        
        if tipo in ['VENDITA', 'XME']:
            if lotto_id:
                cursor.execute("UPDATE lotti SET quantita_attuale = quantita_attuale + ? WHERE id = ?", (qta, lotto_id))
            else:
                cursor.execute("""
                    UPDATE lotti SET quantita_attuale = quantita_attuale + ? 
                    WHERE id = (SELECT id FROM lotti WHERE prodotto_id = ? ORDER BY id DESC LIMIT 1)
                """, (qta, p_id))
        elif tipo == 'CARICO':
            if lotto_id:
                cursor.execute("UPDATE lotti SET quantita_attuale = MAX(0, quantita_attuale - ?) WHERE id = ?", (qta, lotto_id))
        
        cursor.execute("DELETE FROM movimenti WHERE id = ?", (movimento_id,))
        return True, "Movimento stornato con successo!"

def elimina_lotto_db(lotto_id):
    """Elimina definitivamente un lotto e scollega eventuali movimenti associati."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE movimenti SET lotto_id = NULL WHERE lotto_id = ?", (lotto_id,))
        cursor.execute("DELETE FROM lotti WHERE id = ?", (lotto_id,))

# ==========================================
# INTERFACCIA UTENTE (STREAMLIT)
# ==========================================
st.title("📦 Labzz - Gestione Magazzino FIFO")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "💸 Cassa & Movimenti", 
    "📋 Gestione Stock", 
    "🚚 Rifornimenti & Lotti",
    "📊 Dashboard & KPI", 
    "📜 Report & Storico"
])

# ------------------------------------------
# TAB 1: CASSA & REGISTRA MOVIMENTI
# ------------------------------------------
with tab1:
    st.subheader("Cassa Operativa")
    
    tipo_operazione = st.radio("Seleziona Operazione", ["Vendita", "Acquisto", "XME"], horizontal=True)
    
    if tipo_operazione == "Vendita":
        prodotti_disp_df = get_prodotti_disponibili_df()
        
        if prodotti_disp_df.empty:
            st.warning("⚠️ Nessun prodotto disponibile in magazzino da vendere. Aggiungi uno stock nella scheda 'Gestione Stock' o 'Acquisto'.")
        else:
            prod_nome = st.selectbox("Seleziona Prodotto da Vendere", prodotti_disp_df['nome'].tolist())
            prod_row = prodotti_disp_df[prodotti_disp_df['nome'] == prod_nome].iloc[0]
            p_id = int(prod_row['id'])
            
            with get_connection() as conn:
                query_lotti = "SELECT * FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0 ORDER BY data_scadenza ASC, id ASC"
                lotti_disponibili = pd.read_sql_query(query_lotti, conn, params=(p_id,))

            qta_tot_disp = float(lotti_disponibili['quantita_attuale'].sum())
            st.info(f"Disponibilità totale per **{prod_nome}**: **{qta_tot_disp:,.1f} g** su {len(lotti_disponibili)} lotti attivi.")
            
            with st.form("form_vendita"):
                st.markdown("##### Registra Vendita (FIFO Automatico)")
                col1, col2 = st.columns(2)
                
                with col1:
                    quantita_vendita = st.number_input("Quantità da Vendere (g)", min_value=0.5, value=min(100.0, qta_tot_disp), step=0.5, format="%.1f")
                    prezzo_vendita_unitario = st.number_input("Prezzo al grammo (€/g)", min_value=0.1, value=float(prod_row['valore_mercato_unitario']), step=0.5, format="%.2f")
                
                with col2:
                    totale_vendita = quantita_vendita * prezzo_vendita_unitario
                    st.metric("Totale Incasso Previsto", f"€ {totale_vendita:,.2f}")
                    note = st.text_input("Note (Opzionale)")

                if st.form_submit_button("Conferma Vendita FIFO"):
                    if quantita_vendita > qta_tot_disp:
                        st.error(f"Quantità inserita ({quantita_vendita:,.1f} g) superiore alla disponibilità ({qta_tot_disp:,.1f} g).")
                    else:
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            qta_da_scaricare = float(quantita_vendita)
                            
                            for _, lotto in lotti_disponibili.iterrows():
                                if qta_da_scaricare <= 0:
                                    break
                                
                                l_id = int(lotto['id'])
                                qta_lotto_disp = float(lotto['quantita_attuale'])
                                costo_u_lotto = float(lotto['costo_acquisto_unitario'])
                                cod_lotto = lotto['codice_lotto']
                                
                                prelievo = min(qta_lotto_disp, qta_da_scaricare)
                                nuova_qta_lotto = qta_lotto_disp - prelievo
                                qta_da_scaricare -= prelievo
                                
                                costo_quota_parte = prelievo * costo_u_lotto
                                ricavo_quota_parte = prelievo * prezzo_vendita_unitario
                                margine_quota_parte = ricavo_quota_parte - costo_quota_parte
                                
                                cursor.execute("UPDATE lotti SET quantita_attuale = ? WHERE id = ?", (nuova_qta_lotto, l_id))
                                cursor.execute("""
                                    INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, ricavo_totale, costo_totale, margine, note)
                                    VALUES (?, ?, 'VENDITA', ?, ?, ?, ?, ?, ?)
                                """, (p_id, l_id, prelievo, prezzo_vendita_unitario, ricavo_totale, costo_quota_parte, margine_quota_parte, f"Lotto {cod_lotto} | {note}".strip(" |")))
                        
                        st.success(f"✅ Vendita registrata con successo applicando logica FIFO!")
                        st.rerun()

    elif tipo_operazione == "Acquisto":
        prodotti_tutti_df = get_prodotti_df()
        
        if prodotti_tutti_df.empty:
            st.warning("⚠️ Nessun prodotto censito in anagrafica. Crea prima un prodotto nella scheda 'Gestione Stock'.")
        else:
            with st.form("form_carico"):
                st.markdown("##### Registra Acquisto Stock / Nuovo Lotto")
                col1, col2 = st.columns(2)
                
                with col1:
                    prod_nome = st.selectbox("Prodotto", prodotti_tutti_df['nome'].tolist())
                    quantita = st.number_input("Quantità Acquistata (g)", min_value=0.5, value=1000.0, step=0.5, format="%.1f")
                    costo_unitario = st.number_input("Costo d'Acquisto al grammo (€/g)", min_value=0.1, value=1.0, step=0.5, format="%.2f")
                    
                with col2:
                    codice_lotto = st.text_input("Codice Lotto", value=f"LOTTO-{datetime.now().strftime('%Y%m%d-%H%M')}")
                    data_scadenza = st.date_input("Data di Scadenza", value=date.today())
                    note = st.text_input("Note Aggiuntive")

                if st.form_submit_button("Registra Rifornimento"):
                    prod_row = prodotti_tutti_df[prodotti_tutti_df['nome'] == prod_nome].iloc[0]
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
                    
                    st.success(f"✅ Rifornimento registrato! Creato nuovo lotto: {codice_lotto}")
                    st.rerun()

    elif tipo_operazione == "XME":
        lotti_df = get_lotti_attivi_df()
        
        if lotti_df.empty:
            st.error("Nessun lotto con giacenza disponibile per l'operazione XME.")
        else:
            with st.form("form_xme"):
                st.markdown("##### Registra XME")
                
                opzioni_lotto = {f"{r['prodotto']} - Lotto: {r['codice_lotto']} (Disp: {r['quantita_attuale']:,.1f} g)": r['id'] for _, r in lotti_df.iterrows()}
                lotto_selezionato_label = st.selectbox("Seleziona Lotto da Scaricare", list(opzioni_lotto.keys()))
                lotto_id_scelto = opzioni_lotto[lotto_selezionato_label]
                
                lotto_row = lotti_df[lotti_df['id'] == lotto_id_scelto].iloc[0]
                
                qta_xme = st.number_input("Quantità (g)", min_value=0.5, max_value=float(lotto_row['quantita_attuale']), value=10.0, step=0.5, format="%.1f")
                motivo = st.text_input("Note XME", placeholder="Es. Utilizzo personale, Note varie")

                if st.form_submit_button("Conferma XME"):
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        nuova_qta = float(lotto_row['quantita_attuale']) - qta_xme
                        costo_perdita = qta_xme * float(lotto_row['costo_acquisto_unitario'])
                        
                        prodotti_df = get_prodotti_df()
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
    
    df_stato_disponibile = calcola_stato_magazzino(solo_disponibili=True)
    if not df_stato_disponibile.empty:
        sotto_scorta = df_stato_disponibile[df_stato_disponibile['qta_disponibile'] < df_stato_disponibile['scorta_minima_g']]
        if not sotto_scorta.empty:
            for _, r in sotto_scorta.iterrows():
                st.warning(f"⚠️ **Sotto scorta minima!** {r['prodotto']}: attuale {r['qta_disponibile']:,.1f} g (Soglia minima: {r['scorta_minima_g']:,.1f} g)")

    col_a, col_b = st.columns(2)
    
    with col_a:
        with st.expander("➕ **Aggiungi Nuovo Prodotto in Anagrafica**", expanded=False):
            with st.form("form_nuovo_prodotto"):
                nome_nuovo = st.text_input("Nome Prodotto", placeholder="Es. Zafferano, Spezia")
                qta_iniziale = st.number_input("Quantità Iniziale (g)", min_value=0.0, value=0.0, step=0.5, format="%.1f")
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
        with st.expander("⚡ **Modifica / Aggiorna Prodotto Esistente**", expanded=True):
            prodotti_df = get_prodotti_df()
            if prodotti_df.empty:
                st.info("Nessun prodotto censito in anagrafica.")
            else:
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
    
    st.subheader("Giacenza Attuale in Magazzino")
    if df_stato_disponibile.empty:
        st.info("Nessun prodotto con giacenza attualmente disponibile in magazzino.")
    else:
        st.dataframe(
            df_stato_disponibile[[
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
# TAB 3: RIFORNIMENTI & LOTTI
# ------------------------------------------
with tab3:
    st.subheader("🚚 Registro Rifornimenti e Lotti")
    
    storico_lotti_df = get_storico_lotti_df()
    prodotti_tutti_df = get_prodotti_df()
    
    if storico_lotti_df.empty:
        st.info("Nessun lotto di rifornimento registrato.")
    else:
        col_m1, col_m2, col_m3 = st.columns(3)
        costo_tot_lotti = storico_lotti_df['costo_totale_sostenuto'].sum()
        incasso_tot_lotti = storico_lotti_df['incasso_generato'].sum()
        guadagno_netto_tot_lotti = storico_lotti_df['guadagno_netto_lotto'].sum()
        
        col_m1.metric("Costo Totale Rifornimenti", f"€ {costo_tot_lotti:,.2f}")
        col_m2.metric("Incassi Generati dai Lotti", f"€ {incasso_tot_lotti:,.2f}")
        col_m3.metric("Guadagno Netto Rifornimenti", f"€ {guadagno_netto_tot_lotti:,.2f}")
        
        st.markdown("---")
        
        st.dataframe(
            storico_lotti_df[[
                'lotto_id', 'prodotto', 'codice_lotto', 'quantita_iniziale', 'quantita_attuale',
                'unita_misura', 'costo_acquisto_unitario', 'costo_totale_sostenuto',
                'incasso_generato', 'guadagno_netto_lotto', 'data_carico', 'data_scadenza'
            ]],
            column_config={
                "lotto_id": "ID Lotto",
                "prodotto": "Prodotto",
                "codice_lotto": "Codice Lotto",
                "quantita_iniziale": st.column_config.NumberColumn("Q.tà Iniziale", format="%.1f g"),
                "quantita_attuale": st.column_config.NumberColumn("Q.tà Residua", format="%.1f g"),
                "unita_misura": "U.M.",
                "costo_acquisto_unitario": st.column_config.NumberColumn("Costo Unit.", format="€ %.2f"),
                "costo_totale_sostenuto": st.column_config.NumberColumn("Costo Totale", format="€ %.2f"),
                "incasso_generato": st.column_config.NumberColumn("Incasso Generato", format="€ %.2f"),
                "guadagno_netto_lotto": st.column_config.NumberColumn("Guadagno Netto", format="€ %.2f"),
                "data_carico": "Data Carico",
                "data_scadenza": "Data Scadenza"
            },
            use_container_width=True,
            hide_index=True
        )

    st.markdown("---")
    
    # SEZIONE DI GESTIONE IN FONDO ALLA PAGINA
    st.subheader("⚙️ Gestore Lotti (Aggiungi o Rimuovi)")
    
    col_l1, col_l2 = st.columns(2)
    
    with col_l1:
        with st.expander("➕ **Aggiungi un Nuovo Lotto**", expanded=True):
            if prodotti_tutti_df.empty:
                st.warning("Crea prima un prodotto in anagrafica.")
            else:
                with st.form("form_lotto_manuale"):
                    p_nome_lotto = st.selectbox("Seleziona Prodotto", prodotti_tutti_df['nome'].tolist())
                    cod_lotto_m = st.text_input("Codice Lotto", value=f"LOTTO-MAN-{datetime.now().strftime('%Y%m%d-%H%M')}")
                    qta_lotto_m = st.number_input("Quantità Lotto (g)", min_value=0.5, value=500.0, step=0.5, format="%.1f")
                    costo_u_lotto_m = st.number_input("Costo Unitario d'Acquisto (€/g)", min_value=0.1, value=1.0, step=0.5, format="%.2f")
                    data_scad_m = st.date_input("Data di Scadenza Lotto", value=date.today())
                    
                    if st.form_submit_button("➕ Aggiungi Lotto"):
                        p_row_m = prodotti_tutti_df[prodotti_tutti_df['nome'] == p_nome_lotto].iloc[0]
                        p_id_m = int(p_row_m['id'])
                        
                        with get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_carico, data_scadenza)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (p_id_m, cod_lotto_m, qta_lotto_m, qta_lotto_m, costo_u_lotto_m, date.today(), data_scad_m))
                        
                        st.success(f"✅ Lotto '{cod_lotto_m}' aggiunto con successo!")
                        st.rerun()

    with col_l2:
        with st.expander("🗑️ **Elimina un Lotto Esistente**", expanded=True):
            if storico_lotti_df.empty:
                st.info("Nessun lotto presente da rimuovere.")
            else:
                opzioni_lotti_elim = {
                    f"ID {r['lotto_id']} | {r['prodotto']} - Lotto: {r['codice_lotto']} (Disp: {r['quantita_attuale']:,.1f} g)": r['lotto_id']
                    for _, r in storico_lotti_df.iterrows()
                }
                
                label_lotto_scelto = st.selectbox("Seleziona Lotto da Rimuovere", list(opzioni_lotti_elim.keys()))
                id_lotto_scelto = opzioni_lotti_elim[label_lotto_scelto]
                
                lotto_info = storico_lotti_df[storico_lotti_df['lotto_id'] == id_lotto_scelto].iloc[0]
                
                st.warning(f"Sei sicuro di voler eliminare il lotto **{lotto_info['codice_lotto']}**? L'operazione non può essere annullata.")
                
                if st.button("🗑️ Rimuovi Definitivamente Lotto"):
                    elimina_lotto_db(id_lotto_scelto)
                    st.success(f"✅ Lotto '{lotto_info['codice_lotto']}' rimosso con successo!")
                    st.rerun()

# ------------------------------------------
# TAB 4: DASHBOARD & KPI
# ------------------------------------------
with tab4:
    st.subheader("Dashboard & Analytics")
    df_stato_disp = calcola_stato_magazzino(solo_disponibili=True)
    lotti_attivi_df = get_lotti_attivi_df()
    movimenti_df = get_movimenti_df()

    if df_stato_disp.empty and movimenti_df.empty:
        st.info("Nessun dato di magazzino o movimento disponibile.")
    else:
        if not df_stato_disp.empty:
            sotto_scorta_dash = df_stato_disp[df_stato_disp['qta_disponibile'] < df_stato_disp['scorta_minima_g']]
            if not sotto_scorta_dash.empty:
                for _, r in sotto_scorta_dash.iterrows():
                    st.warning(f"⚠️ **Sotto scorta minima!** {r['prodotto']}: attuale {r['qta_disponibile']:,.1f} g (Scorta Minima: {r['scorta_minima_g']:,.1f} g)")

        if not lotti_attivi_df.empty:
            lotti_attivi_df['data_scadenza'] = pd.to_datetime(lotti_attivi_df['data_scadenza'])
            oggi = pd.to_datetime(date.today())
            lotti_in_scadenza = lotti_attivi_df[(lotti_attivi_df['data_scadenza'] - oggi).dt.days <= 15]
            
            if not lotti_in_scadenza.empty:
                for _, row in lotti_in_scadenza.iterrows():
                    giorni = (row['data_scadenza'] - oggi).days
                    msg = f"In scadenza tra {giorni} giorni!" if giorni >= 0 else "SCADUTO!"
                    st.error(f"🚨 **Lotto {row['codice_lotto']} ({row['prodotto']})**: {msg} (Data: {row['data_scadenza'].strftime('%Y-%m-%d')})")

        col1, col2, col3, col4 = st.columns(4)
        val_costo = df_stato_disp['valore_totale_costo'].sum() if not df_stato_disp.empty else 0
        val_mercato = df_stato_disp['valore_totale_mercato'].sum() if not df_stato_disp.empty else 0
        incasso_tot = movimenti_df[movimenti_df['tipo'] == 'VENDITA']['ricavo_totale'].sum() if not movimenti_df.empty else 0
        margine_tot = movimenti_df[movimenti_df['tipo'] == 'VENDITA']['margine'].sum() if not movimenti_df.empty else 0

        col1.metric("Valore Magazzino (Costo)", f"€ {val_costo:,.2f}")
        col2.metric("Valore Magazzino (Vendita)", f"€ {val_mercato:,.2f}")
        col3.metric("Incasso Totale Vendite", f"€ {incasso_tot:,.2f}")
        col4.metric("Margine Netto Effettivo", f"€ {margine_tot:,.2f}")

        st.markdown("---")

        col_g1, col_g2 = st.columns(2)

        with col_g1:
            st.subheader("📈 Storico Progressivo Operazioni")
            if movimenti_df.empty:
                st.info("Registra almeno una transazione per generare il grafico.")
            else:
                mov_df = movimenti_df.copy()
                mov_df['Data_Ora'] = pd.to_datetime(mov_df['data'])
                mov_df = mov_df.sort_values('Data_Ora')
                
                mov_df['Spesi Totali'] = mov_df['costo_totale'].cumsum()
                mov_df['Incasso Totale'] = mov_df['ricavo_totale'].cumsum()
                mov_df['Margine Netto'] = mov_df['margine'].cumsum()
                
                chart_df = mov_df.melt(
                    id_vars=['Data_Ora', 'prodotto', 'tipo'],
                    value_vars=['Spesi Totali', 'Incasso Totale', 'Margine Netto'],
                    var_name='Metrica',
                    value_name='Valore (€)'
                )

                chart = alt.Chart(chart_df).mark_line(point=True).encode(
                    x=alt.X('Data_Ora:T', title='Data e Ora Transazione'),
                    y=alt.Y('Valore (€):Q', title='Importo (€)'),
                    color=alt.Color('Metrica:N', legend=alt.Legend(title="Legenda")),
                    tooltip=['Data_Ora:T', 'prodotto:N', 'tipo:N', 'Metrica:N', 'Valore (€):Q']
                ).properties(height=380).interactive()

                st.altair_chart(chart, use_container_width=True)

        with col_g2:
            st.subheader("📊 Guadagno Netto per Singolo Lotto")
            storico_lotti = get_storico_lotti_df()
            if storico_lotti.empty:
                st.info("Nessun lotto disponibile per il grafico.")
            else:
                chart_lotti = alt.Chart(storico_lotti).mark_bar().encode(
                    x=alt.X('codice_lotto:N', title='Codice Lotto', sort=None),
                    y=alt.Y('guadagno_netto_lotto:Q', title='Guadagno Netto (€)'),
                    color=alt.condition(
                        alt.datum.guadagno_netto_lotto >= 0,
                        alt.value("#2ed573"),
                        alt.value("#ff4757")
                    ),
                    tooltip=['codice_lotto:N', 'prodotto:N', 'costo_totale_sostenuto:Q', 'incasso_generato:Q', 'guadagno_netto_lotto:Q']
                ).properties(height=380)

                st.altair_chart(chart_lotti, use_container_width=True)

# ------------------------------------------
# TAB 5: REPORT & STORICO
# ------------------------------------------
with tab5:
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
                'id', 'data', 'prodotto', 'codice_lotto', 'tipo', 'quantita', 'unita_misura',
                'prezzo_unitario', 'ricavo_totale', 'costo_totale', 'margine', 'note'
            ]],
            column_config={
                "id": "ID",
                "data": "Data/Ora",
                "prodotto": "Prodotto",
                "codice_lotto": "Lotto",
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