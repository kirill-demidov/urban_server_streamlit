import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
import requests
import os
import common
import config
from youtube_search import get_youtube_search_links

st.set_page_config(
    page_title="Urban Server Analytics",
    page_icon="📊",
    layout="wide"
)

# Конфигурация
SCHEMA_NAME = config.schema_name
API_BASE_URL = config.URL.rstrip('/')  # Убираем trailing slash, если он есть

def send_rest(endpoint):
    """
    Отправка REST запроса к API
    """
    try:
        response = requests.get(f"{API_BASE_URL}/{endpoint}")
        return response.text, response.ok, response.status_code
    except Exception as e:
        return str(e), False, 500

@st.cache_data(ttl=3600)  # Кэшируем данные на 1 час
def load_data():
    """
    Загрузка данных из базы данных
    """
    try:
        ans, is_ok, status_code = send_rest(f'v2/select/{SCHEMA_NAME}/nsi_list?column_order=id')
        if not is_ok:
            st.error('Ошибка при получении данных из БД')
            st.warning(f"URL запроса: {API_BASE_URL}/v2/select/{SCHEMA_NAME}/nsi_list?column_order=id")
            st.warning(f"HTTP-код ответа: {status_code}")
            st.warning(f"Ответ сервера: {ans}")
            return None
        
        # Преобразуем JSON в список словарей
        data = json.loads(ans)
        
        # Создаем DataFrame
        df = pd.DataFrame(data)
        
        # Выводим информацию о дубликатах
        st.write(f"Всего видео: {len(df)}")
        
        try:
            # Создаем новый DataFrame с уникальными значениями
            df_unique = df.drop_duplicates(subset=['id_site'], keep='last')
            
            # Переименовываем колонки для удобства
            df_unique = df_unique.rename(columns={
                'video_published_at': 'published_at',
                'id_site': 'video_id',
                'sh_name': 'title',
                'likes': 'likes_count',
                'dislikes': 'dislikes_count',
                'comments_count': 'comments_count',
                'views_count': 'views_count',
                'sentiment': 'sentiment',
                'value': 'sentiment_value',
                'channel_title': 'channel_title',
                'video_duration': 'duration'
            })
            
            # Преобразуем даты
            df_unique['published_at'] = pd.to_datetime(df_unique['published_at'], errors='coerce')
            
            # Преобразуем длительность видео
            def parse_duration(duration):
                if pd.isna(duration):
                    return "00:00"
                try:
                    # Убираем 'PT' из начала
                    duration = duration.replace('PT', '')
                    minutes = 0
                    seconds = 0
                    
                    # Обрабатываем минуты
                    if 'M' in duration:
                        minutes_part = duration.split('M')[0]
                        minutes = int(minutes_part)
                        duration = duration.split('M')[1]
                    
                    # Обрабатываем секунды
                    if 'S' in duration:
                        seconds_part = duration.split('S')[0]
                        seconds = int(seconds_part)
                    
                    return f"{minutes:02d}:{seconds:02d}"
                except:
                    return "00:00"
            
            df_unique['duration'] = df_unique['duration'].apply(parse_duration)
            
            # Преобразуем числовые значения
            numeric_columns = ['views_count', 'likes_count', 'dislikes_count', 'comments_count']
            for col in numeric_columns:
                df_unique[col] = pd.to_numeric(df_unique[col], errors='coerce').fillna(0)
            
            # Удаляем строки с пропущенными датами
            df_unique = df_unique.dropna(subset=['published_at'])
            
            return df_unique
            
        except Exception as e:
            st.error(f"Ошибка при преобразовании данных: {str(e)}")
            st.error(f"Тип ошибки: {type(e)}")
            import traceback
            st.error(f"Traceback: {traceback.format_exc()}")
            return None
            
    except Exception as e:
        st.error(f'Ошибка при обработке данных: {str(e)}')
        st.error(f'Тип ошибки: {type(e)}')
        import traceback
        st.error(f'Traceback: {traceback.format_exc()}')
        return None

def create_sentiment_distribution(df):
    """
    Создание графика распределения настроений
    """
    sentiment_counts = df['sentiment'].value_counts()
    
    fig = px.pie(
        values=sentiment_counts.values,
        names=sentiment_counts.index,
        title='Распределение настроений в видео',
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    
    fig.update_traces(textposition='inside', textinfo='percent+label')
    return fig

def create_engagement_metrics(df):
    """
    Создание графика метрик вовлеченности
    """
    engagement_data = df.groupby('video_id').agg({
        'views_count': 'first',
        'likes_count': 'first',
        'dislikes_count': 'first',
        'comments_count': 'first'
    }).reset_index()
    
    fig = go.Figure()
    
    metrics = {
        'views_count': 'Просмотры',
        'likes_count': 'Лайки',
        'dislikes_count': 'Дизлайки',
        'comments_count': 'Комментарии'
    }
    
    for col, name in metrics.items():
        fig.add_trace(go.Bar(
            name=name,
            y=[engagement_data[col].mean()],
            x=[name],
            text=[f"{engagement_data[col].mean():,.0f}"],
            textposition='auto',
        ))
    
    fig.update_layout(
        title='Средние показатели вовлеченности',
        barmode='group',
        showlegend=False,
        yaxis_title='Количество'
    )
    
    return fig

def create_views_timeline(df):
    """
    Создание графика просмотров во времени
    """
    try:
        # Создаем копию DataFrame для работы
        df_timeline = df.copy()
        
        # Проверяем наличие колонки published_at
        if 'published_at' not in df_timeline.columns:
            st.error("Колонка published_at не найдена")
            return None
        
        # Проверяем на дубликаты
        if df_timeline['published_at'].duplicated().any():
            st.warning("Обнаружены дубликаты в датах публикации")
            # Добавляем уникальный идентификатор к дубликатам
            df_timeline['published_at'] = df_timeline.apply(
                lambda row: f"{row['published_at']}_{row['video_id']}", 
                axis=1
            )
        
        # Сортируем по дате
        df_timeline = df_timeline.sort_values('published_at')
        
        fig = px.line(
            df_timeline,
            x='published_at',
            y='views_count',
            title='Количество просмотров по времени публикации',
            labels={'views_count': 'Просмотры', 'published_at': 'Дата публикации'}
        )
        
        return fig
    except Exception as e:
        st.error(f"Ошибка при создании графика: {str(e)}")
        return None

def create_top_channels(df):
    """
    Создание графика топ каналов
    """
    channel_stats = df.groupby('channel_title').agg({
        'video_id': 'count',
        'views_count': 'sum',
        'likes_count': 'sum'
    }).reset_index()
    
    channel_stats = channel_stats.sort_values('views_count', ascending=False).head(10)
    
    fig = px.bar(
        channel_stats,
        x='channel_title',
        y='views_count',
        title='Топ-10 каналов по просмотрам',
        labels={'views_count': 'Просмотры', 'channel_title': 'Канал'},
        color='likes_count',
        color_continuous_scale='Viridis'
    )
    
    fig.update_layout(xaxis_tickangle=-45)
    return fig

def main():
    st.title("📊 Анализ YouTube просмотров")
    
    # Загрузка данных
    df = load_data()
    
    if df is None:
        st.error("Не удалось загрузить данные")
        return
    
    # Фильтры для всего приложения
    st.sidebar.header("Фильтры")
    
    # Фильтр по дате
    min_date = df['published_at'].min().date()
    max_date = df['published_at'].max().date()
    
    # Добавляем выбор типа фильтра по дате
    date_filter_type = st.sidebar.radio(
        "Тип фильтра по дате",
        ["Произвольный период", "Относительный период"]
    )
    
    if date_filter_type == "Относительный период":
        relative_period = st.sidebar.selectbox(
            "Выберите период",
            ["Последние 7 дней", "Последние 30 дней", "Последние 90 дней", "Последние 180 дней", "Последние 365 дней"]
        )
        
        # Вычисляем даты на основе выбранного периода
        end_date = max_date  # Используем максимальную дату из данных
        if relative_period == "Последние 7 дней":
            start_date = end_date - pd.Timedelta(days=7)
        elif relative_period == "Последние 30 дней":
            start_date = end_date - pd.Timedelta(days=30)
        elif relative_period == "Последние 90 дней":
            start_date = end_date - pd.Timedelta(days=90)
        elif relative_period == "Последние 180 дней":
            start_date = end_date - pd.Timedelta(days=180)
        else:  # Последние 365 дней
            start_date = end_date - pd.Timedelta(days=365)
            
        date_range = (start_date, end_date)
    else:
        date_range = st.sidebar.date_input(
            "Период",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )
    
    # Фильтр по каналу
    channels = ['Все каналы'] + sorted(df['channel_title'].unique().tolist())
    selected_channel = st.sidebar.selectbox("Канал", channels)
    
    # Фильтр по настроению
    sentiments = ['Все настроения'] + sorted(df['sentiment'].unique().tolist())
    selected_sentiment = st.sidebar.selectbox("Настроение", sentiments)
    
    # Фильтр по количеству просмотров
    min_views = int(df['views_count'].min())
    max_views = int(df['views_count'].max())
    views_range = st.sidebar.slider(
        "Количество просмотров",
        min_value=min_views,
        max_value=max_views,
        value=(min_views, max_views)
    )
    
    # Общие настройки сортировки
    st.sidebar.header("Настройки отображения")
    sort_by = st.sidebar.selectbox(
        "Сортировать по",
        options=['Просмотры', 'Лайки', 'Комментарии', 'Дата публикации'],
        index=0
    )
    sort_order = st.sidebar.selectbox(
        "Порядок сортировки",
        options=['По убыванию', 'По возрастанию'],
        index=0
    )
    
    # Выбор колонок для отображения
    columns_to_show = st.sidebar.multiselect(
        "Выберите колонки для отображения",
        options=df.columns.tolist(),
        default=['title', 'channel_title', 'published_at', 'views_count', 'likes_count', 'comments_count', 'sentiment']
    )
    
    # Применяем фильтры
    filtered_df = df.copy()
    
    # Фильтр по дате
    if len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = filtered_df[
            (filtered_df['published_at'].dt.date >= start_date) &
            (filtered_df['published_at'].dt.date <= end_date)
        ]
    
    # Фильтр по каналу
    if selected_channel != 'Все каналы':
        filtered_df = filtered_df[filtered_df['channel_title'] == selected_channel]
    
    # Фильтр по настроению
    if selected_sentiment != 'Все настроения':
        filtered_df = filtered_df[filtered_df['sentiment'] == selected_sentiment]
    
    # Фильтр по просмотрам
    filtered_df = filtered_df[
        (filtered_df['views_count'] >= views_range[0]) &
        (filtered_df['views_count'] <= views_range[1])
    ]
    
    # Применяем сортировку
    sort_columns = {
        'Просмотры': 'views_count',
        'Лайки': 'likes_count',
        'Комментарии': 'comments_count',
        'Дата публикации': 'published_at'
    }
    
    sort_column = sort_columns[sort_by]
    ascending = sort_order == 'По возрастанию'
    filtered_df = filtered_df.sort_values(by=sort_column, ascending=ascending)
    
    # Основные метрики
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Всего видео", len(filtered_df))
    with col2:
        st.metric("Общее количество просмотров", f"{filtered_df['views_count'].sum():,}")
    with col3:
        st.metric("Общее количество лайков", f"{filtered_df['likes_count'].sum():,}")
    with col4:
        st.metric("Общее количество комментариев", f"{filtered_df['comments_count'].sum():,}")
    
    # Дополнительные метрики
    col1, col2 = st.columns(2)
    with col1:
        avg_views = filtered_df['views_count'].mean()
        st.metric("Среднее количество просмотров", f"{avg_views:,.0f}")
    with col2:
        engagement_rate = (filtered_df['likes_count'].sum() + filtered_df['comments_count'].sum()) / filtered_df['views_count'].sum() * 100
        st.metric("Уровень вовлеченности", f"{engagement_rate:.2f}%")
    
    # Графики
    st.plotly_chart(create_engagement_metrics(filtered_df), use_container_width=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(create_sentiment_distribution(filtered_df), use_container_width=True)
    with col2:
        st.plotly_chart(create_top_channels(filtered_df), use_container_width=True)
    
    timeline_fig = create_views_timeline(filtered_df)
    if timeline_fig is not None:
        st.plotly_chart(timeline_fig, use_container_width=True)
    
    # Детальная статистика по отдельному видео
    st.subheader("Детальная статистика по видео")
    
    # Выбор видео
    video_titles = filtered_df['title'].tolist()
    selected_video = st.selectbox(
        "Выберите видео для детального анализа",
        options=video_titles,
        index=0
    )
    
    if selected_video:
        video_data = filtered_df[filtered_df['title'] == selected_video].iloc[0]
        
        # Создаем вкладки для разных типов информации
        tab1, tab2 = st.tabs(["Основная информация", "Комментарии"])
        
        with tab1:
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Основная информация:**")
                st.write(f"**Название:** {video_data['title']}")
                st.write(f"**Канал:** {video_data['channel_title']}")
                st.write(f"**Дата публикации:** {video_data['published_at'].strftime('%d.%m.%Y %H:%M')}")
                st.write(f"**Длительность:** {video_data['duration']}")
                st.write(f"**Настроение:** {video_data['sentiment']}")
                st.write(f"**Значение настроения:** {video_data['sentiment_value']}")
                
            with col2:
                st.write("**Метрики:**")
                st.write(f"**Просмотры:** {video_data['views_count']:,}")
                st.write(f"**Лайки:** {video_data['likes_count']:,}")
                st.write(f"**Дизлайки:** {video_data['dislikes_count']:,}")
                st.write(f"**Комментарии:** {video_data['comments_count']:,}")
                
                # Расчет дополнительных метрик
                like_ratio = video_data['likes_count'] / video_data['views_count'] * 100 if video_data['views_count'] > 0 else 0
                comment_ratio = video_data['comments_count'] / video_data['views_count'] * 100 if video_data['views_count'] > 0 else 0
                st.write(f"**Процент лайков:** {like_ratio:.2f}%")
                st.write(f"**Процент комментариев:** {comment_ratio:.2f}%")
            
            # Ссылка на видео
            st.write(f"**Ссылка на видео:** [{video_data['url']}]({video_data['url']})")
            
            # Описание видео
            if 'description' in video_data and video_data['description']:
                st.write("**Описание видео:**")
                st.write(video_data['description'])
        
        with tab2:
            st.write("**Комментарии:**")
            if 'comments' in video_data and video_data['comments']:
                for comment in video_data['comments']:
                    st.write(f"**{comment['author']}** ({comment['published_at']}):")
                    st.write(comment['text'])
                    st.write("---")
            else:
                st.write("Комментарии отсутствуют")
    
    # Детальные данные
    st.subheader("Детальные данные")
    
    # Отображаем данные
    if columns_to_show:
        st.dataframe(
            filtered_df[columns_to_show],
            use_container_width=True,
            height=400
        )
    else:
        st.warning("Выберите хотя бы одну колонку для отображения")

if __name__ == '__main__':
    main() 