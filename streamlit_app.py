import hmac
from io import BytesIO

import pandas as pd
import streamlit as st


def to_xlsx_bytes(df: pd.DataFrame, sheet_name: str = 'Sheet1') -> bytes:
    """Конвертує DataFrame у байти xlsx."""
    buf = BytesIO()
    df_out = df.copy()
    # tz-aware datetime — Excel не вміє, прибираємо tz якщо є
    for col in df_out.select_dtypes(include=['datetimetz']).columns:
        df_out[col] = df_out[col].dt.tz_localize(None)
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df_out.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return buf.getvalue()


XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

st.set_page_config(page_title='Аналіз угод', layout='wide')


def check_password() -> bool:
    """Авторизація — пароль зі st.secrets['password']."""
    def password_entered():
        if hmac.compare_digest(str(st.session_state.get('password', '')),
                               str(st.secrets['password'])):
            st.session_state['password_correct'] = True
            del st.session_state['password']
        else:
            st.session_state['password_correct'] = False

    if st.session_state.get('password_correct'):
        return True

    st.markdown(
        """
        <style>
        [data-testid="stToolbar"] { display: none; }
        section.main > div.block-container { padding-top: 5rem; }
        div[data-testid="stForm"] {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 16px;
            padding: 1.6rem 1.6rem 1.2rem;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
        }
        div[data-testid="stForm"] button[kind="primary"] {
            width: 100%;
            border-radius: 10px;
            padding: 0.55rem 0;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown(
            "<div style='text-align:center; font-size:2.2rem;'>🔒</div>"
            "<h2 style='text-align:center; margin:0 0 0.25rem;'>Доступ до звіту</h2>"
            "<p style='text-align:center; color:#64748b; margin:0 0 1rem;'>"
            "Введіть пароль для перегляду аналізу угод</p>",
            unsafe_allow_html=True,
        )

        with st.form('login_form', clear_on_submit=False):
            st.text_input('Пароль', type='password',
                          key='password', placeholder='Введіть пароль')
            submitted = st.form_submit_button('Увійти', type='primary',
                                              use_container_width=True)
            if submitted:
                password_entered()
                st.rerun()

        if st.session_state.get('password_correct') is False:
            st.error('Невірний пароль')

    return False


if not check_password():
    st.stop()

st.title('Аналіз угод з кількома рахунками')


@st.cache_data
def load_data(path: str = 'result.csv') -> pd.DataFrame:
    df = pd.read_csv(path, encoding='utf-8-sig')
    df = df.rename(columns={'НомерСделки': 'НомерУгоди',
                            'ДатаСделки': 'ДатаУгоди'})

    # 1С зберігає дати зі зсувом +2000 років (4024 → 2024).
    def fix_year(s):
        if pd.isna(s):
            return s
        return f'{int(s[:4]) - 2000:04d}{s[4:]}'

    for col in ['ДатаУгоди', 'ДатаСчета']:
        df[col] = pd.to_datetime(df[col].map(fix_year),
                                 format='%Y-%m-%d %H:%M:%S',
                                 errors='coerce')
    df['МесяцСчета'] = df['ДатаСчета'].dt.to_period('M').astype(str)
    df = df.drop(columns=['Сумма'], errors='ignore')
    return df


df = load_data()

c1, c2, c3 = st.columns(3)
c1.metric('Рядків', len(df))
c2.metric('Унікальних угод', df['НомерУгоди'].nunique())
c3.metric('Діапазон дат угод',
          f"{df['ДатаУгоди'].min():%Y-%m-%d} … {df['ДатаУгоди'].max():%Y-%m-%d}")

tab1, tab2, tab3 = st.tabs([
    'Повний датасет де рахунків >1',
    'Різні місяці в рахунках',
    'Різні місяці в рахунках з 2026 року',
])

with tab1:
    st.subheader('Повний датасет із result.csv')
    st.dataframe(df, use_container_width=True, height=600)
    st.download_button(
        '⬇️ Завантажити XLSX (повний датасет)',
        data=to_xlsx_bytes(df, 'Повний датасет'),
        file_name='повний_датасет.xlsx',
        mime=XLSX_MIME,
        key='dl_full',
    )

    st.subheader('ТОП-20 угод за кількістю рахунків')
    top = (df[['НомерУгоди', 'ДатаУгоди', 'КолвоСчетов']]
             .drop_duplicates()
             .sort_values('КолвоСчетов', ascending=False)
             .head(20))
    st.dataframe(top, use_container_width=True)
    st.download_button(
        '⬇️ Завантажити XLSX (ТОП-20)',
        data=to_xlsx_bytes(top, 'ТОП-20'),
        file_name='top20_угод.xlsx',
        mime=XLSX_MIME,
        key='dl_top',
    )

with tab2:
    st.subheader('Угоди, де рахунки виставлені в різні місяці')

    угоди_разные_месяцы = (
        df.groupby('НомерУгоди')['МесяцСчета']
          .nunique()
          .loc[lambda s: s > 1]
          .index
    )
    df_diff = (df[df['НомерУгоди'].isin(угоди_разные_месяцы)]
                 .sort_values(['НомерУгоди', 'ДатаСчета'])
                 .reset_index(drop=True))

    m1, m2 = st.columns(2)
    m1.metric('Угод з різними місяцями', df_diff['НомерУгоди'].nunique())
    m2.metric('Рядків (рахунків)', len(df_diff))

    st.dataframe(df_diff, use_container_width=True, height=600)
    st.download_button(
        '⬇️ Завантажити XLSX (різні місяці)',
        data=to_xlsx_bytes(df_diff, 'Різні місяці'),
        file_name='угоди_різні_місяці.xlsx',
        mime=XLSX_MIME,
        key='dl_diff',
    )

    # збережемо для tab3
    st.session_state['df_diff'] = df_diff

with tab3:
    st.subheader('Угоди з різними місяцями рахунків з 2026-01-01')

    df_diff = st.session_state.get('df_diff')
    if df_diff is None:
        # на випадок якщо вкладка відкрита першою
        угоди_разные_месяцы = (
            df.groupby('НомерУгоди')['МесяцСчета']
              .nunique()
              .loc[lambda s: s > 1]
              .index
        )
        df_diff = df[df['НомерУгоди'].isin(угоди_разные_месяцы)]

    угоди_2026 = (
        df_diff[df_diff['ДатаУгоди'] >= '2026-01-01']
          .groupby(['НомерУгоди', 'ДатаУгоди'], as_index=False)
          .agg(КолвоСчетов=('НомерСчета', 'count'),
               КолвоМесяцев=('МесяцСчета', 'nunique'))
          .sort_values('ДатаУгоди')
    )

    st.metric('Кількість угод з 2026-01-01', len(угоди_2026))
    st.dataframe(угоди_2026, use_container_width=True, height=600)
    st.download_button(
        '⬇️ Завантажити XLSX (угоди з 2026)',
        data=to_xlsx_bytes(угоди_2026, 'Угоди 2026'),
        file_name='угоди_2026.xlsx',
        mime=XLSX_MIME,
        key='dl_2026',
    )
