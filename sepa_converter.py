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
    # --- 1) Detect the column names in your CSV ---
    cols = {c.lower(): c for c in df.columns}
    # Beneficiary name
    benef_col = next((v for k, v in cols.items() if "beneficiary name" in k), None)
    # IBAN (or “Beneficiary account”)
    iban_col = next((v for k, v in cols.items() if "iban" in k or "beneficiary account" in k), None)
    # Amount
    amount_col = next((v for k, v in cols.items() if k == "amount"), None)
    # Reference (structured)
    ref_col = cols.get("reference")
    # Payment description (unstructured)
    desc_col = next((v for k, v in cols.items() if "description" in k), None)

    # Drop rows missing the absolute essentials
    df = df.dropna(subset=[iban_col, amount_col])

    # Convert Amount to float
    df["Amount_Clean"] = (
        df[amount_col].astype(str)
                         .str.replace(",", ".")
                         .str.replace(" ", "")
                         .astype(float)
    )

    # Header values
    ctrl_sum = df["Amount_Clean"].sum()
    now_iso  = datetime.now().isoformat()
    msg_id   = f"MSG{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # --- 2) Build XML skeleton ---
    NS = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.09"
    root = ET.Element("Document", xmlns=NS)
    cstmr = ET.SubElement(root, "CstmrCdtTrfInitn")

    # Group Header
    grp = ET.SubElement(cstmr, "GrpHdr")
    ET.SubElement(grp, "MsgId").text      = msg_id
    ET.SubElement(grp, "CreDtTm").text    = now_iso
    ET.SubElement(grp, "NbOfTxs").text    = str(len(df))
    ET.SubElement(grp, "CtrlSum").text    = f"{ctrl_sum:.2f}"
    initg = ET.SubElement(grp, "InitgPty")
    ET.SubElement(initg, "Nm").text       = debtor_name

    # Payment Information
    pmt = ET.SubElement(cstmr, "PmtInf")
    ET.SubElement(pmt, "PmtInfId").text   = f"PmtInf{datetime.now().strftime('%Y%m%d%H%M%S')}"
    ET.SubElement(pmt, "PmtMtd").text     = "TRF"
    ET.SubElement(pmt, "BtchBookg").text  = "true"
    ET.SubElement(pmt, "NbOfTxs").text    = str(len(df))
    ET.SubElement(pmt, "CtrlSum").text    = f"{ctrl_sum:.2f}"
    pti = ET.SubElement(pmt, "PmtTpInf")
    svc = ET.SubElement(pti, "SvcLvl")
    ET.SubElement(svc, "Cd").text         = "SEPA"
    ET.SubElement(pmt, "ReqdExctnDt").text= datetime.now().strftime("%Y-%m-%d")

    # Debtor
    dbtr = ET.SubElement(pmt, "Dbtr")
    ET.SubElement(dbtr, "Nm").text        = debtor_name
    dbac = ET.SubElement(pmt, "DbtrAcct")
    dbid = ET.SubElement(dbac, "Id")
    ET.SubElement(dbid, "IBAN").text      = debtor_iban
    dagt = ET.SubElement(pmt, "DbtrAgt")
    fin  = ET.SubElement(dagt, "FinInstnId")
    ET.SubElement(fin, "BIC").text        = debtor_bic
    ET.SubElement(pmt, "ChrgBr").text     = "SLEV"

    # --- 3) Per-row Credit Transfer blocks ---
    for idx, row in df.iterrows():
        cdt = ET.SubElement(pmt, "CdtTrfTxInf")

        # 3a) Payment ID
        pid = ET.SubElement(cdt, "PmtId")
        # pick structured reference if given, else description, else auto-fallback
        if ref_col and pd.notna(row[ref_col]) and str(row[ref_col]).strip():
            ref = str(row[ref_col]).strip()[:35]
        elif desc_col and pd.notna(row[desc_col]) and str(row[desc_col]).strip():
            ref = str(row[desc_col]).strip()[:35]
        else:
            ref = f"TRX-{idx+1:05d}"
        ET.SubElement(pid, "EndToEndId").text = ref

        # 3b) Amount
        amt = ET.SubElement(cdt, "Amt")
        inst = ET.SubElement(amt, "InstdAmt", Ccy=currency)
        inst.text = f"{row['Amount_Clean']:.2f}"

        # 3c) Creditor (beneficiary)
        cdr = ET.SubElement(cdt, "Cdtr")
        nm  = row.get(benef_col, "")
        ET.SubElement(cdr, "Nm").text        = str(nm)[:70]
        cac = ET.SubElement(cdt, "CdtrAcct")
        cid = ET.SubElement(cac, "Id")
        ET.SubElement(cid, "IBAN").text      = row[iban_col]

        # 3d) Remittance Information
        rmt = ET.SubElement(cdt, "RmtInf")
        ET.SubElement(rmt, "Ustrd").text     = ref

        strd = ET.SubElement(rmt, "Strd")
        cri  = ET.SubElement(strd, "CdtrRefInf")
        tp   = ET.SubElement(cri, "Tp")
        cop  = ET.SubElement(tp, "CdOrPrtry")
        ET.SubElement(cop, "Cd").text        = "SCOR"
        ET.SubElement(cri, "Ref").text       = ref

    # --- 4) Write file ---
    out = f"sepa_{msg_id}.xml"
    ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)
    return out

def main():
    st.title("SEPA XML Generator for LHV Bank")
    st.sidebar.header("Debtor Information")
    debtor_name = st.sidebar.text_input("Debtor Name")
    debtor_iban = st.sidebar.text_input("Debtor IBAN")
    debtor_bic  = st.sidebar.text_input("Debtor BIC")
    currency    = st.sidebar.text_input("Currency", "EUR")

    st.header("Upload Payouts CSV")
    uploaded = st.file_uploader("Choose a CSV file", type="csv")
    if uploaded:
        df = pd.read_csv(uploaded)
        st.write("Detected columns:", list(df.columns))
        if st.button("Generate SEPA XML"):
            if not all([debtor_name, debtor_iban, debtor_bic]):
                st.error("Fill in all debtor fields in the sidebar.")
            else:
                xml_file = generate_sepa_xml(df, debtor_name, debtor_iban, currency, debtor_bic)
                st.success(f"Generated `{xml_file}`")
                with open(xml_file, "rb") as f:
                    st.download_button("Download XML", f, file_name=xml_file, mime="application/xml")

if __name__ == "__main__":
    main()
