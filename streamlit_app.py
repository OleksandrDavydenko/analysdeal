import hmac

import pandas as pd
import streamlit as st

st.set_page_config(page_title='Аналіз сделок', layout='wide')


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
        [data-testid="stHeader"], [data-testid="stToolbar"] { display: none; }
        .block-container { padding-top: 4rem; max-width: 460px; }
        .login-card {
            background: linear-gradient(180deg, #ffffff 0%, #f7f9fc 100%);
            border: 1px solid rgba(0,0,0,0.06);
            border-radius: 18px;
            padding: 2.2rem 2rem 1.6rem;
            box-shadow: 0 12px 40px rgba(15, 23, 42, 0.08);
            margin-top: 2rem;
        }
        .login-icon {
            font-size: 2.4rem;
            text-align: center;
            margin-bottom: 0.4rem;
        }
        .login-title {
            text-align: center;
            font-size: 1.45rem;
            font-weight: 700;
            color: #0f172a;
            margin: 0;
        }
        .login-sub {
            text-align: center;
            color: #64748b;
            font-size: 0.92rem;
            margin: 0.3rem 0 1.4rem;
        }
        .stTextInput > div > div > input {
            border-radius: 10px !important;
            padding: 0.65rem 0.9rem !important;
        }
        .stButton > button {
            width: 100%;
            border-radius: 10px;
            padding: 0.55rem 0;
            background: #2563eb;
            color: white;
            border: none;
            font-weight: 600;
        }
        .stButton > button:hover { background: #1d4ed8; color: white; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.markdown('<div class="login-icon">🔒</div>', unsafe_allow_html=True)
        st.markdown('<p class="login-title">Доступ до звіту</p>',
                    unsafe_allow_html=True)
        st.markdown('<p class="login-sub">Введіть пароль для перегляду аналізу сделок</p>',
                    unsafe_allow_html=True)

        with st.form('login_form', clear_on_submit=False):
            st.text_input('Пароль', type='password',
                          key='password', label_visibility='collapsed',
                          placeholder='Пароль')
            submitted = st.form_submit_button('Увійти')
            if submitted:
                password_entered()
                st.rerun()

        if st.session_state.get('password_correct') is False:
            st.error('Невірний пароль')
        st.markdown('</div>', unsafe_allow_html=True)

    return False


if not check_password():
    st.stop()

st.title('Аналіз сделок з кількома рахунками')


@st.cache_data
def load_data(path: str = 'result.csv') -> pd.DataFrame:
    df = pd.read_csv(path, encoding='utf-8-sig')

    # 1С зберігає дати зі зсувом +2000 років (4024 → 2024).
    def fix_year(s):
        if pd.isna(s):
            return s
        return f'{int(s[:4]) - 2000:04d}{s[4:]}'

    for col in ['ДатаСделки', 'ДатаСчета']:
        df[col] = pd.to_datetime(df[col].map(fix_year),
                                 format='%Y-%m-%d %H:%M:%S',
                                 errors='coerce')
    df['МесяцСчета'] = df['ДатаСчета'].dt.to_period('M').astype(str)
    return df


df = load_data()

c1, c2, c3 = st.columns(3)
c1.metric('Рядків', len(df))
c2.metric('Унікальних сделок', df['НомерСделки'].nunique())
c3.metric('Діапазон дат угод',
          f"{df['ДатаСделки'].min():%Y-%m-%d} … {df['ДатаСделки'].max():%Y-%m-%d}")

tab1, tab2, tab3 = st.tabs([
    'Крок 1. Повний датасет',
    'Крок 2. Різні місяці рахунків',
    'Крок 3. Угоди з 2026 року',
])

with tab1:
    st.subheader('Повний датасет із result.csv')
    st.dataframe(df, use_container_width=True, height=600)

    st.subheader('ТОП-20 сделок за кількістю рахунків')
    top = (df.groupby(['НомерСделки', 'ДатаСделки', 'КолвоСчетов'], as_index=False)
             .agg(СуммаПоСчетам=('Сумма', 'sum'))
             .sort_values('КолвоСчетов', ascending=False)
             .head(20))
    st.dataframe(top, use_container_width=True)

with tab2:
    st.subheader('Угоди, де рахунки виставлені в різні місяці')

    сделки_разные_месяцы = (
        df.groupby('НомерСделки')['МесяцСчета']
          .nunique()
          .loc[lambda s: s > 1]
          .index
    )
    df_diff = (df[df['НомерСделки'].isin(сделки_разные_месяцы)]
                 .sort_values(['НомерСделки', 'ДатаСчета'])
                 .reset_index(drop=True))

    m1, m2 = st.columns(2)
    m1.metric('Угод з різними місяцями', df_diff['НомерСделки'].nunique())
    m2.metric('Рядків (рахунків)', len(df_diff))

    st.dataframe(df_diff, use_container_width=True, height=600)

    # збережемо для tab3
    st.session_state['df_diff'] = df_diff

with tab3:
    st.subheader('Угоди з різними місяцями рахунків з 2026-01-01')

    df_diff = st.session_state.get('df_diff')
    if df_diff is None:
        # на випадок якщо вкладка відкрита першою
        сделки_разные_месяцы = (
            df.groupby('НомерСделки')['МесяцСчета']
              .nunique()
              .loc[lambda s: s > 1]
              .index
        )
        df_diff = df[df['НомерСделки'].isin(сделки_разные_месяцы)]

    сделки_2026 = (
        df_diff[df_diff['ДатаСделки'] >= '2026-01-01']
          .groupby(['НомерСделки', 'ДатаСделки'], as_index=False)
          .agg(КолвоСчетов=('НомерСчета', 'count'),
               КолвоМесяцев=('МесяцСчета', 'nunique'),
               СуммаПоСчетам=('Сумма', 'sum'))
          .sort_values('ДатаСделки')
    )

    st.metric('Кількість угод з 2026-01-01', len(сделки_2026))
    st.dataframe(сделки_2026, use_container_width=True, height=600)
