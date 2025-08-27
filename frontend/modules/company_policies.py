import streamlit as st
import pandas as pd
from frontend.utils.ui_helpers import fix_merged_text, sanitize_html

def page():
    # st.title("Company Policies Reference")  # Removed duplicate header
    st.markdown(sanitize_html(fix_merged_text(
        "This page provides quick reference to key internal company policies for recruiters during candidate screening calls. All data below is **sample data for POC purposes**."
    )), unsafe_allow_html=True)

    st.header("Pay Bands (Sample)")
    pay_bands = [
        {"Level": "Junior", "Engineering": "$80,000 - $110,000", "Product": "$75,000 - $100,000", "Design": "$70,000 - $95,000"},
        {"Level": "Mid", "Engineering": "$110,000 - $145,000", "Product": "$100,000 - $135,000", "Design": "$95,000 - $125,000"},
        {"Level": "Senior", "Engineering": "$145,000 - $190,000", "Product": "$135,000 - $175,000", "Design": "$125,000 - $165,000"},
        {"Level": "Lead / Manager", "Engineering": "$190,000 - $240,000", "Product": "$175,000 - $220,000", "Design": "$165,000 - $210,000"},
    ]
    df = pd.DataFrame(pay_bands)
    st.table(df)

    st.header("Company Benefits (Sample)")
    st.markdown(sanitize_html(fix_merged_text(
        """
        - **Health Insurance**: Comprehensive medical, dental, and vision coverage for employees and dependents
        - **Paid Time Off**: 20 vacation days, 10 company holidays, unlimited sick days
        - **401(k) Plan**: 5% company match, immediate vesting
        - **Parental Leave**: 16 weeks paid leave for primary caregivers, 6 weeks for secondary
        - **Remote Work**: Flexible remote/hybrid policies available
        """
    )), unsafe_allow_html=True)

    st.header("Relocation Guide (Sample)")
    st.markdown(sanitize_html(fix_merged_text(
        """
        - **Relocation Assistance**: Up to $10,000 for moving expenses
        - **Temporary Housing**: Up to 30 days provided
        - **Local Orientation**: City tours, school search assistance, and settling-in services
        """
    )), unsafe_allow_html=True)

    st.header("Immigration & Visa Policies (Sample)")
    st.markdown(sanitize_html(fix_merged_text(
        """
        - **Sponsorship**: H-1B, TN, and Green Card sponsorship available for eligible roles
        - **Legal Support**: In-house immigration counsel and external legal partners
        - **Timeline Guidance**: Typical H-1B process takes 3-6 months; green card PERM process 12-24 months
        - **Dependents**: Visa and relocation support for dependents included
        """
    )), unsafe_allow_html=True)

    st.info(sanitize_html(fix_merged_text(
        "For official and up-to-date policies, please refer to the HR portal or contact People Operations."
    )))
