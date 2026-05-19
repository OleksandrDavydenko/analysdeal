import hmac

import pandas as pd
import streamlit as st

st.set_page_config(page_title='Аналіз сделок', layout='wide')


def check_password() -> bool:
    """Проста авторизація — пароль зі st.secrets['password']."""
    def password_entered():
        if hmac.compare_digest(st.session_state.get('password', ''),
                               st.secrets['password']):
            st.session_state['password_correct'] = True
            del st.session_state['password']
        else:
            st.session_state['password_correct'] = False

    if st.session_state.get('password_correct'):
        return True

    st.text_input('Пароль', type='password',
                  on_change=password_entered, key='password')
    if st.session_state.get('password_correct') is False:
        st.error('Невірний пароль')
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
