import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime

def generate_sepa_xml(df: pd.DataFrame,
                      debtor_name: str,
                      debtor_iban: str,
                      currency: str,
                      debtor_bic: str) -> str:
    """
    Build a pain.001.001.09 SEPA XML file with both unstructured (Ustrd)
    and structured (Strd/CdtrRefInf) references.
    Returns the filename of the written XML.
    """
    # Clean and convert amounts
    df = df.dropna(subset=["IBAN", "Amount"])
    df["Amount_Corrected"] = (
        df["Amount"].astype(str)
             .str.replace(",", ".")
             .str.replace(" ", "")
             .astype(float)
    )

    # Header values
    ctrl_sum = df["Amount_Corrected"].sum()
    now_iso = datetime.now().isoformat()
    msg_id = f"MSG{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Root & Customer Credit Transfer Initiation
    root = ET.Element("Document",
                      xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.09")
    cstmr_cdt_trf_initn = ET.SubElement(root, "CstmrCdtTrfInitn")

    # Group Header
    grp_hdr = ET.SubElement(cstmr_cdt_trf_initn, "GrpHdr")
    ET.SubElement(grp_hdr, "MsgId").text = msg_id
    ET.SubElement(grp_hdr, "CreDtTm").text = now_iso
    ET.SubElement(grp_hdr, "NbOfTxs").text = str(len(df))
    ET.SubElement(grp_hdr, "CtrlSum").text = f"{ctrl_sum:.2f}"
    initg_pty = ET.SubElement(grp_hdr, "InitgPty")
    ET.SubElement(initg_pty, "Nm").text = debtor_name

    # Payment Information
    pmt_inf = ET.SubElement(cstmr_cdt_trf_initn, "PmtInf")
    ET.SubElement(pmt_inf, "PmtInfId").text = f"PmtInf{datetime.now().strftime('%Y%m%d%H%M%S')}"
    ET.SubElement(pmt_inf, "PmtMtd").text = "TRF"
    ET.SubElement(pmt_inf, "BtchBookg").text = "true"
    ET.SubElement(pmt_inf, "NbOfTxs").text = str(len(df))
    ET.SubElement(pmt_inf, "CtrlSum").text = f"{ctrl_sum:.2f}"
    pmt_tp_inf = ET.SubElement(pmt_inf, "PmtTpInf")
    svc_lvl = ET.SubElement(pmt_tp_inf, "SvcLvl")
    ET.SubElement(svc_lvl, "Cd").text = "SEPA"
    ET.SubElement(pmt_inf, "ReqdExctnDt").text = datetime.now().strftime("%Y-%m-%d")

    # Debtor (your) details
    dbtr = ET.SubElement(pmt_inf, "Dbtr")
    ET.SubElement(dbtr, "Nm").text = debtor_name
    dbtr_acct = ET.SubElement(pmt_inf, "DbtrAcct")
    dbtr_acct_id = ET.SubElement(dbtr_acct, "Id")
    ET.SubElement(dbtr_acct_id, "IBAN").text = debtor_iban
    dbtr_agt = ET.SubElement(pmt_inf, "DbtrAgt")
    fin_instn_id = ET.SubElement(dbtr_agt, "FinInstnId")
    ET.SubElement(fin_instn_id, "BIC").text = debtor_bic
    ET.SubElement(pmt_inf, "ChrgBr").text = "SLEV"

    # Individual Credit Transfer Txns
    for idx, row in df.iterrows():
        cdt_trf_tx_inf = ET.SubElement(pmt_inf, "CdtTrfTxInf")
        # Payment ID
        pmt_id = ET.SubElement(cdt_trf_tx_inf, "PmtId")
        remit = str(row.get("CLRHS-42 2025-05-16", "")).strip()
        reference = remit[:35] if remit else f"TRX-{idx+1:05d}"
        ET.SubElement(pmt_id, "EndToEndId").text = reference

        # Amount
        amt = ET.SubElement(cdt_trf_tx_inf, "Amt")
        instd_amt = ET.SubElement(amt, "InstdAmt", Ccy=currency)
        instd_amt.text = f"{row['Amount_Corrected']:.2f}"

        # Creditor
        cdtr = ET.SubElement(cdt_trf_tx_inf, "Cdtr")
        ET.SubElement(cdtr, "Nm").text = row["CreditorName"][:70]
        cdtr_acct = ET.SubElement(cdt_trf_tx_inf, "CdtrAcct")
        cdtr_id = ET.SubElement(cdtr_acct, "Id")
        ET.SubElement(cdtr_id, "IBAN").text = row["IBAN"]

        # Remittance Information (both unstructured and structured)
        rmt_inf = ET.SubElement(cdt_trf_tx_inf, "RmtInf")
        ET.SubElement(rmt_inf, "Ustrd").text = reference

        strd = ET.SubElement(rmt_inf, "Strd")
        cdtr_ref_inf = ET.SubElement(strd, "CdtrRefInf")
        tp = ET.SubElement(cdtr_ref_inf, "Tp")
        cd_or_prtry = ET.SubElement(tp, "CdOrPrtry")
        ET.SubElement(cd_or_prtry, "Cd").text = "SCOR"
        ET.SubElement(cdtr_ref_inf, "Ref").text = reference

    # Write out the XML
    output_file = f"sepa_{msg_id}.xml"
    ET.ElementTree(root).write(
        output_file,
        encoding="utf-8",
        xml_declaration=True
    )
    return output_file

def main():
    st.title("SEPA XML Generator for LHV Bank")
    st.sidebar.header("Debtor Information")
    debtor_name = st.sidebar.text_input("Debtor Name")
    debtor_iban = st.sidebar.text_input("Debtor IBAN")
    debtor_bic  = st.sidebar.text_input("Debtor BIC")
    currency    = st.sidebar.text_input("Currency", "EUR")

    st.header("Upload Payouts CSV")
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.markdown("**Columns expected:** `CreditorName`, `IBAN`, `Amount`, `CLRHS-42 2025-05-16`")
        if st.button("Generate SEPA XML"):
            if not all([debtor_name, debtor_iban, debtor_bic]):
                st.error("Please fill in all debtor fields in the sidebar.")
            else:
                output_file = generate_sepa_xml(
                    df, debtor_name, debtor_iban, currency, debtor_bic
                )
                st.success(f"SEPA XML generated: `{output_file}`")
                with open(output_file, "rb") as f:
                    st.download_button(
                        "Download XML",
                        f,
                        file_name=output_file,
                        mime="application/xml"
                    )

if __name__ == "__main__":
    main()
