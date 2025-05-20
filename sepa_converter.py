import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime
import os

def generate_sepa_xml(df, debtor_name, debtor_iban, currency, bic):
    df = df.dropna(subset=["IBAN", "Amount"])
    df["Amount_Corrected"] = df["Amount"].str.replace(",", ".").str.replace(" ", "").astype(float)
    control_sum = df["Amount_Corrected"].sum()

    message_id = f"MSG{datetime.now().strftime('%Y%m%d%H%M%S')}"

    root = ET.Element("Document", xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.09")
    cstmr_cdt_trf_initn = ET.SubElement(root, "CstmrCdtTrfInitn")

    grp_hdr = ET.SubElement(cstmr_cdt_trf_initn, "GrpHdr")
    ET.SubElement(grp_hdr, "MsgId").text = message_id
    ET.SubElement(grp_hdr, "CreDtTm").text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    ET.SubElement(grp_hdr, "NbOfTxs").text = str(len(df))
    ET.SubElement(grp_hdr, "CtrlSum").text = f"{control_sum:.2f}"
    initg_pty = ET.SubElement(grp_hdr, "InitgPty")
    ET.SubElement(initg_pty, "Nm").text = debtor_name

    pmt_inf = ET.SubElement(cstmr_cdt_trf_initn, "PmtInf")
    ET.SubElement(pmt_inf, "PmtInfId").text = message_id
    ET.SubElement(pmt_inf, "PmtMtd").text = "TRF"
    ET.SubElement(pmt_inf, "BtchBookg").text = "false"
    ET.SubElement(pmt_inf, "NbOfTxs").text = str(len(df))
    ET.SubElement(pmt_inf, "CtrlSum").text = f"{control_sum:.2f}"

    pmt_tp_inf = ET.SubElement(pmt_inf, "PmtTpInf")
    svc_lvl = ET.SubElement(pmt_tp_inf, "SvcLvl")
    ET.SubElement(svc_lvl, "Cd").text = "SEPA"

    reqd_exctn_dt = ET.SubElement(pmt_inf, "ReqdExctnDt")
    ET.SubElement(reqd_exctn_dt, "Dt").text = datetime.now().strftime('%Y-%m-%d')

    dbtr = ET.SubElement(pmt_inf, "Dbtr")
    ET.SubElement(dbtr, "Nm").text = debtor_name
    dbtr_acct = ET.SubElement(pmt_inf, "DbtrAcct")
    id_elem = ET.SubElement(dbtr_acct, "Id")
    ET.SubElement(id_elem, "IBAN").text = debtor_iban
    dbtr_agt = ET.SubElement(pmt_inf, "DbtrAgt")
    fin_instn_id = ET.SubElement(dbtr_agt, "FinInstnId")
    ET.SubElement(fin_instn_id, "BICFI").text = bic

    ET.SubElement(pmt_inf, "ChrgBr").text = "SLEV"

    for idx, row in df.iterrows():
        cdt_trf_tx_inf = ET.SubElement(pmt_inf, "CdtTrfTxInf")
        pmt_id = ET.SubElement(cdt_trf_tx_inf, "PmtId")
        ET.SubElement(pmt_id, "EndToEndId").text = row["RemittanceInfo"][:35] if pd.notna(row["RemittanceInfo"]) else f"TRX-{idx+1:05d}"

        amt = ET.SubElement(cdt_trf_tx_inf, "Amt")
        instd_amt = ET.SubElement(amt, "InstdAmt", Ccy=currency)
        amount_value = float(row["Amount"].replace(",", "."))
        instd_amt.text = f"{amount_value:.2f}"

        cdtr = ET.SubElement(cdt_trf_tx_inf, "Cdtr")
        ET.SubElement(cdtr, "Nm").text = row["CreditorName"][:70]

        cdtr_acct = ET.SubElement(cdt_trf_tx_inf, "CdtrAcct")
        cdtr_id = ET.SubElement(cdtr_acct, "Id")
        ET.SubElement(cdtr_id, "IBAN").text = row["IBAN"]

        rmt_inf = ET.SubElement(cdt_trf_tx_inf, "RmtInf")
        ET.SubElement(rmt_inf, "Ustrd").text = ""

    output_file = f"sepa_{message_id}.xml"
    ET.ElementTree(root).write(output_file, encoding="utf-8", xml_declaration=True)
    return output_file

# Streamlit Interface
st.title("SEPA XML Converter (pain.001.001.09)")

uploaded_file = st.file_uploader("Upload CSV", type="csv")

with st.expander("Advanced Settings"):
    debtor_name = st.text_input("Debtor Name", value="Ryft Pay Ltd")
    debtor_iban = st.text_input("Debtor IBAN", value="GB78LHVB04031500000634")
    currency = st.text_input("Currency", value="GBP")
    bic = st.text_input("BIC", value="LHVBGB2L")

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.write("Preview of Uploaded Data:")
    st.dataframe(df.head())

    st.write("### Map Your Columns")
    col_names = df.columns.tolist()

    col_creditor = st.selectbox("Creditor Name Column", col_names, index=4)
    col_iban = st.selectbox("IBAN Column", col_names, index=35)
    col_amount = st.selectbox("Amount Column", col_names, index=13)
    col_remittance = st.selectbox("Remittance Info Column", col_names, index=36)

    if st.button("Generate SEPA XML"):
        df_sepa = pd.DataFrame({
            "CreditorName": df[col_creditor],
            "IBAN": df[col_iban],
            "Amount": df[col_amount],
            "RemittanceInfo": df[col_remittance]
        })

        xml_file = generate_sepa_xml(df_sepa, debtor_name, debtor_iban, currency, bic)

        with open(xml_file, "rb") as f:
            st.download_button(
                label="📥 Download SEPA XML", 
                data=f,
                file_name=xml_file,
                mime="application/xml"
            )
        os.remove(xml_file)
