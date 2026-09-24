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
# GESTIONE DATABASE SQLITE PERSISTENTE
# ==========================================
def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    """Inizializza e aggiorna le tabelle nel database magazzino.db."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Anagrafica prodotti
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prodotti (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL,
        unita_misura TEXT DEFAULT 'g',
        valore_mercato_unitario REAL DEFAULT 0
    )
    """)
    
    # Normalizza l'unità di misura a grammi ('g') per tutti i prodotti esistenti
    cursor.execute("UPDATE prodotti SET unita_misura = 'g'")
    
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
    
    # 3. Registro movimenti (carico, vendita, scarto)
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
    
    # Inserisce i prodotti base solo se il database è completamente nuovo
    cursor.execute("SELECT COUNT(*) FROM prodotti")
    if cursor.fetchone()[0] == 0:
        prodotti_iniziali = [
            ("Farina", "g", 0.0015),
            ("Zucchero", "g", 0.0012),
            ("Cioccolata", "g", 0.0085),
            ("Fieno", "g", 0.00018)
        ]
        cursor.executemany("""
            INSERT INTO prodotti (nome, unita_misura, valore_mercato_unitario)
            VALUES (?, ?, ?)
        """, prodotti_iniziali)
    
    conn.commit()
    conn.close()

init_db()

# ==========================================
# FUNZIONI UTILITY DATI
# ==========================================
def get_prodotti_df():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM prodotti", conn)
    conn.close()
    return df

def get_lotti_df():
    conn = get_connection()
    query = """
        SELECT l.id, p.nome AS prodotto, l.codice_lotto, l.quantita_attuale, 
               'g' AS unita_misura, l.costo_acquisto_unitario, l.data_carico, l.data_scadenza
        FROM lotti l
        JOIN prodotti p ON l.prodotto_id = p.id
        WHERE l.quantita_attuale > 0
        ORDER BY l.data_scadenza ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_movimenti_df():
    conn = get_connection()
    query = """
        SELECT m.id, m.data, p.nome AS prodotto, m.tipo, m.quantita, 'g' AS unita_misura,
               m.prezzo_unitario, m.ricavo_totale, m.costo_totale, m.margine, m.note
        FROM movimenti m
        JOIN prodotti p ON m.prodotto_id = p.id
        ORDER BY m.data DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def calcola_stato_magazzino():
    conn = get_connection()
    prodotti_df = pd.read_sql_query("SELECT * FROM prodotti", conn)
    lotti_df = pd.read_sql_query("SELECT * FROM lotti WHERE quantita_attuale > 0", conn)
    movimenti_df = pd.read_sql_query("SELECT * FROM movimenti", conn)
    conn.close()

    risultati = []
    
    for _, prod in prodotti_df.iterrows():
        p_id = prod['id']
        lotti_prod = lotti_df[lotti_df['prodotto_id'] == p_id]
        
        qta_totale = lotti_prod['quantita_attuale'].sum()
        valore_costo_totale = (lotti_prod['quantita_attuale'] * lotti_prod['costo_acquisto_unitario']).sum()
        costo_medio_ponderato = (valore_costo_totale / qta_totale) if qta_totale > 0 else 0
        valore_mercato_totale = qta_totale * prod['valore_mercato_unitario']
        
        vendite = movimenti_df[(movimenti_df['prodotto_id'] == p_id) & (movimenti_df['tipo'] == 'VENDITA')]
        qta_venduta = vendite['quantita'].sum()
        incasso_totale = vendite['ricavo_totale'].sum()
        margine_totale = vendite['margine'].sum()

        risultati.append({
            'prodotto_id': p_id,
            'prodotto': prod['nome'],
            'unita_misura': 'g',
            'qta_disponibile': qta_totale,
            'costo_medio_ponderato': costo_medio_ponderato,
            'valore_mercato_unitario': prod['valore_mercato_unitario'],
            'valore_totale_costo': valore_costo_totale,
            'valore_totale_mercato': valore_mercato_totale,
            'qta_venduta': qta_venduta,
            'incasso_totale': incasso_totale,
            'margine_totale': margine_totale
        })

    return pd.DataFrame(risultati)

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
    
    tipo_operazione = st.radio("Seleziona Operazione", ["Vendita", "Acquisto", "Registra Scarto"], horizontal=True)
    prodotti_df = get_prodotti_df()
    
    if prodotti_df.empty:
        st.warning("Nessun prodotto presente in anagrafica. Aggiungi un prodotto dalla scheda 'Gestione Stock'.")
    else:
        # 1. VENDITA
        if tipo_operazione == "Vendita":
            prod_nome = st.selectbox("Seleziona Prodotto da Vendere", prodotti_df['nome'].tolist())
            prod_row = prodotti_df[prodotti_df['nome'] == prod_nome].iloc[0]
            p_id = int(prod_row['id'])
            
            conn = get_connection()
            query_lotti = "SELECT * FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0 ORDER BY data_scadenza ASC"
            lotti_disponibili = pd.read_sql_query(query_lotti, conn, params=(p_id,))
            conn.close()

            if lotti_disponibili.empty:
                st.error(f"⚠️ Nessuna disponibilità in magazzino per **{prod_nome}**.")
            else:
                qta_tot_disp = lotti_disponibili['quantita_attuale'].sum()
                st.info(f"Disponibilità attuale per **{prod_nome}**: **{qta_tot_disp:,.0f} g**")
                
                with st.form("form_vendita"):
                    st.markdown("##### Registra Vendita")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        quantita_vendita = st.number_input("Quantità da Vendere (g)", min_value=1.0, value=100.0, step=10.0)
                        prezzo_vendita_unitario = st.number_input("Prezzo al grammo (€/g)", min_value=0.0001, value=float(prod_row['valore_mercato_unitario']), format="%.4f")
                    
                    with col2:
                        totale_vendita = quantita_vendita * prezzo_vendita_unitario
                        st.metric("Totale Incasso Previsto", f"€ {totale_vendita:,.2f}")
                        note = st.text_input("Note (Opzionale)")

                    if st.form_submit_button("Vendita"):
                        if quantita_vendita > qta_tot_disp:
                            st.error(f"Quantità inserita ({quantita_vendita:,.0f} g) superiore alla disponibilità ({qta_tot_disp:,.0f} g).")
                        else:
                            conn = get_connection()
                            cursor = conn.cursor()
                            
                            qta_rimanente = quantita_vendita
                            costo_totale_acquisto = 0.0
                            
                            for _, lotto in lotti_disponibili.iterrows():
                                if qta_rimanente <= 0:
                                    break
                                
                                l_id = lotto['id']
                                qta_lotto = lotto['quantita_attuale']
                                costo_u = lotto['costo_acquisto_unitario']
                                
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
                            
                            conn.commit()
                            conn.close()
                            st.success(f"✅ Vendita registrata! Incasso: €{ricavo_totale:,.2f} | Margine: €{margine:,.2f}")
                            st.rerun()

        # 2. ACQUISTO
        elif tipo_operazione == "Acquisto":
            with st.form("form_carico"):
                st.markdown("##### Registra Acquisto Stock")
                col1, col2 = st.columns(2)
                
                with col1:
                    prod_nome = st.selectbox("Prodotto", prodotti_df['nome'].tolist())
                    quantita = st.number_input("Quantità Acquistata (g)", min_value=1.0, value=1000.0, step=100.0)
                    costo_unitario = st.number_input("Costo d'Acquisto al grammo (€/g)", min_value=0.0001, value=0.0010, format="%.4f")
                    
                with col2:
                    codice_lotto = st.text_input("Codice Lotto", value=f"LOTTO-{datetime.now().strftime('%Y%m%d-%H%M')}")
                    data_scadenza = st.date_input("Data di Scadenza", value=date.today())
                    note = st.text_input("Note Aggiuntive")

                if st.form_submit_button("Acquisto"):
                    prod_row = prodotti_df[prodotti_df['nome'] == prod_nome].iloc[0]
                    p_id = int(prod_row['id'])
                    
                    conn = get_connection()
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
                    
                    conn.commit()
                    conn.close()
                    st.success(f"✅ Acquisto registrato col lotto {codice_lotto}!")
                    st.rerun()

        # 3. REGISTRA SCARTO
        elif tipo_operazione == "Registra Scarto":
            lotti_df = get_lotti_df()
            
            if lotti_df.empty:
                st.error("Nessun lotto disponibile da cui scaricare scarti.")
            else:
                with st.form("form_scarto"):
                    st.markdown("##### Registra Calo Peso / Scarto")
                    
                    opzioni_lotto = {f"{r['prodotto']} - Lotto: {r['codice_lotto']} (Disp: {r['quantita_attuale']:.0f} g)": r['id'] for _, r in lotti_df.iterrows()}
                    lotto_selezionato_label = st.selectbox("Seleziona Lotto da Scaricare", list(opzioni_lotto.keys()))
                    lotto_id_scelto = opzioni_lotto[lotto_selezionato_label]
                    
                    lotto_row = lotti_df[lotti_df['id'] == lotto_id_scelto].iloc[0]
                    
                    qta_scarto = st.number_input("Quantità da Scartare (g)", min_value=1.0, max_value=float(lotto_row['quantita_attuale']), value=10.0, step=5.0)
                    motivo = st.text_input("Motivazione Scarto", placeholder="Es. Calo peso, Sacchetto rotto")

                    if st.form_submit_button("Conferma Scarto"):
                        conn = get_connection()
                        cursor = conn.cursor()
                        
                        nuova_qta = lotto_row['quantita_attuale'] - qta_scarto
                        costo_perdita = qta_scarto * lotto_row['costo_acquisto_unitario']
                        
                        p_id = int(prodotti_df[prodotti_df['nome'] == lotto_row['prodotto']].iloc[0]['id'])
                        
                        cursor.execute("UPDATE lotti SET quantita_attuale = ? WHERE id = ?", (nuova_qta, lotto_id_scelto))
                        
                        cursor.execute("""
                            INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, prezzo_unitario, costo_totale, margine, note)
                            VALUES (?, ?, 'SCARTO', ?, 0, ?, ?, ?)
                        """, (p_id, lotto_id_scelto, qta_scarto, costo_perdita, -costo_perdita, f"SCARTO: {motivo}"))
                        
                        conn.commit()
                        conn.close()
                        st.warning(f"Scarto registrato! Perdita generata: €{costo_perdita:,.2f}")
                        st.rerun()

# ------------------------------------------
# TAB 2: GESTIONE STOCK & AGGIUNTA RAPIDA
# ------------------------------------------
with tab2:
    st.subheader("📋 Gestione dello Stock (Unità: Grammi - g)")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        with st.expander("➕ **Aggiungi Nuovo Prodotto**", expanded=False):
            with st.form("form_nuovo_prodotto"):
                nome_nuovo = st.text_input("Nome Prodotto", placeholder="Es. Zafferano, Spezia")
                qta_iniziale = st.number_input("Quantità Iniziale (g)", min_value=0.0, value=1000.0, step=100.0)
                costo_u_init = st.number_input("Costo d'Acquisto al grammo (€/g)", min_value=0.0001, value=0.0050, format="%.4f")
                prezzo_v_init = st.number_input("Prezzo di Vendita al grammo (€/g)", min_value=0.0001, value=0.0100, format="%.4f")
                
                if st.form_submit_button("Crea Prodotto"):
                    if nome_nuovo.strip() == "":
                        st.error("Inserisci un nome valido.")
                    else:
                        conn = get_connection()
                        cursor = conn.cursor()
                        try:
                            cursor.execute("INSERT INTO prodotti (nome, unita_misura, valore_mercato_unitario) VALUES (?, 'g', ?)", (nome_nuovo.strip(), prezzo_v_init))
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
                                
                            conn.commit()
                            st.success(f"Prodotto '{nome_nuovo}' salvato con successo!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Un prodotto con questo nome esiste già.")
                        finally:
                            conn.close()

    with col_b:
        with st.expander("⚡ **Aggiorna Quantità / Prezzo Prodotto Esistente**", expanded=True):
            prodotti_df = get_prodotti_df()
            if not prodotti_df.empty:
                prod_mod_nome = st.selectbox("Seleziona Prodotto da Modificare", prodotti_df['nome'].tolist())
                p_row = prodotti_df[prodotti_df['nome'] == prod_mod_nome].iloc[0]
                p_id = int(p_row['id'])
                
                conn = get_connection()
                lotti_p = pd.read_sql_query("SELECT * FROM lotti WHERE prodotto_id = ? AND quantita_attuale > 0", conn, params=(p_id,))
                conn.close()
                
                qta_attuale_tot = lotti_p['quantita_attuale'].sum() if not lotti_p.empty else 0.0
                costo_u_att = (lotti_p['quantita_attuale'] * lotti_p['costo_acquisto_unitario']).sum() / qta_attuale_tot if qta_attuale_tot > 0 else 0.0010

                with st.form("form_rettifica_diretta"):
                    nuova_qta_tot = st.number_input("Nuova Quantità Totale (g)", min_value=0.0, value=float(qta_attuale_tot), step=50.0)
                    nuovo_costo_grammo = st.number_input("Costo d'Acquisto Unitario (€/g)", min_value=0.0001, value=float(costo_u_att if costo_u_att > 0 else 0.0010), format="%.4f")
                    nuovo_prezzo_grammo = st.number_input("Prezzo di Vendita Unitario (€/g)", min_value=0.0001, value=float(p_row['valore_mercato_unitario']), format="%.4f")
                    
                    if st.form_submit_button("Salva Modifiche"):
                        conn = get_connection()
                        cursor = conn.cursor()
                        
                        cursor.execute("UPDATE prodotti SET valore_mercato_unitario = ? WHERE id = ?", (nuovo_prezzo_grammo, p_id))
                        cursor.execute("UPDATE lotti SET quantita_attuale = 0 WHERE prodotto_id = ?", (p_id,))
                        
                        if nuova_qta_tot > 0:
                            cod_lotto_rett = f"RETT-{datetime.now().strftime('%Y%m%d-%H%M')}"
                            cursor.execute("""
                                INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_carico)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (p_id, cod_lotto_rett, nuova_qta_tot, nuova_qta_tot, nuovo_costo_grammo, date.today()))
                        
                        conn.commit()
                        conn.close()
                        st.success(f"Stock di '{prod_mod_nome}' aggiornato!")
                        st.rerun()

    st.markdown("---")
    
    # TABELLA PRODOTTI E GIACENZE
    st.subheader("Giacenza Attuale")
    df_stato = calcola_stato_magazzino()
    
    st.dataframe(
        df_stato[[
            'prodotto', 'qta_disponibile', 'unita_misura',
            'costo_medio_ponderato', 'valore_mercato_unitario',
            'valore_totale_costo', 'valore_totale_mercato'
        ]].rename(columns={
            'prodotto': 'Prodotto',
            'qta_disponibile': 'Quantità (g)',
            'unita_misura': 'U.M.',
            'costo_medio_ponderato': 'Costo Medio (€/g)',
            'valore_mercato_unitario': 'Prezzo Vendita (€/g)',
            'valore_totale_costo': 'Valore Costo (€)',
            'valore_totale_mercato': 'Valore Vendita (€)'
        }),
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

    # Metrics
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
            prod_filtro = st.multiselect("Filtra per Prodotto", opzioni=movimenti_df['prodotto'].unique(), default=movimenti_df['prodotto'].unique())
        with col_f2:
            tipo_filtro = st.multiselect("Filtra per Tipo Operazione", opzioni=movimenti_df['tipo'].unique(), default=movimenti_df['tipo'].unique())
            
        df_filtrato = movimenti_df[
            (movimenti_df['prodotto'].isin(prod_filtro)) & 
            (movimenti_df['tipo'].isin(tipo_filtro))
        ]

        st.dataframe(
            df_filtrato.rename(columns={
                'data': 'Data/Ora',
                'prodotto': 'Prodotto',
                'tipo': 'Tipo',
                'quantita': 'Quantità (g)',
                'unita_misura': 'U.M.',
                'prezzo_unitario': 'Prezzo Unit. (€/g)',
                'ricavo_totale': 'Ricavo (€)',
                'costo_totale': 'Costo (€)',
                'margine': 'Margine (€)',
                'note': 'Note'
            }),
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