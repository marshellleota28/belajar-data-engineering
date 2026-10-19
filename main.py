import os
import requests
import pandas as pd
from datetime import datetime
from google.cloud import bigquery
# ==========================================
# KONFIGURASI BIGQUERY
# ==========================================
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "credentials.json"
PROJECT_ID = "agile-extension-510003-j0"
DATASET_ID = "weather_data"
TABLE_ID = "jakarta_daily_weather"
# ==========================================
# 1. EXTRACT
# ==========================================
def extract_data():
    print("Mengambil data dari Open-Meteo API...")
    # Koordinat Jakarta
    latitude = -6.2088
    longitude = 106.8456
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={latitude}"
        f"&longitude={longitude}"
        "&daily=temperature_2m_max,temperature_2m_min,rain_sum"
        "&timezone=Asia%2FBangkok"
        "&forecast_days=7"
    )
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Gagal mengambil data. Status code: {response.status_code}")
# ==========================================
# 2. TRANSFORM
# ==========================================
def transform_data(raw_json):
    print("Membersihkan dan mengubah format data...")
    daily_data = raw_json["daily"]
    df = pd.DataFrame({
        "tanggal": pd.to_datetime(daily_data["time"]),
        "suhu_maksimal_c": daily_data["temperature_2m_max"],
        "suhu_minimal_c": daily_data["temperature_2m_min"],
        "total_hujan_mm": daily_data["rain_sum"]
    })
    # Mengisi nilai kosong dengan 0
    # df.fillna(0, inplace=True)
    # Waktu proses ETL
    df["diperbarui_pada"] = datetime.now()
    return df

def validate_data(df):
    print("\n===== DATA QUALITY CHECK =====")

    # 1. Cek data kosong
    if df.empty:
        raise Exception("Data kosong!")

    # 2. Cek NULL
    if df.isnull().any().any():
        raise Exception("Ditemukan nilai NULL dalam data!")

    # 3. Cek tanggal duplikat
    if df["tanggal"].duplicated().any():
        raise Exception("Ditemukan tanggal duplikat!")

    # 4. Cek suhu maksimal
    if ((df["suhu_maksimal_c"] < 0) | (df["suhu_maksimal_c"] > 50)).any():
        raise Exception("Ditemukan suhu maksimal yang tidak valid!")

    # 5. Cek suhu minimal
    if ((df["suhu_minimal_c"] < 0) | (df["suhu_minimal_c"] > 50)).any():
        raise Exception("Ditemukan suhu minimal yang tidak valid!")

    # 6. Cek logika suhu
    if (df["suhu_minimal_c"] > df["suhu_maksimal_c"]).any():
        raise Exception("Suhu minimal lebih besar dari suhu maksimal!")

    # 7. Cek curah hujan
    if (df["total_hujan_mm"] < 0).any():
        raise Exception("Ditemukan curah hujan negatif!")

    print("Semua data quality check berhasil!")
    
#DATA QUALITY REPORT
def generate_quality_report(df):
    print("\n===== DATA QUALITY REPORT =====")

    total_rows = len(df)

    null_values = df.isnull().sum().sum()

    duplicate_dates = df["tanggal"].duplicated().sum()

    invalid_max_temp = (
        (df["suhu_maksimal_c"] < 0) |
        (df["suhu_maksimal_c"] > 50)
    ).sum()

    invalid_min_temp = (
        (df["suhu_minimal_c"] < 0) |
        (df["suhu_minimal_c"] > 50)
    ).sum()

    invalid_temp_logic = (
        df["suhu_minimal_c"] > df["suhu_maksimal_c"]
    ).sum()

    negative_rainfall = (
        df["total_hujan_mm"] < 0
    ).sum()

    print(f"Total rows          : {total_rows}")
    print(f"NULL values         : {null_values}")
    print(f"Duplicate dates     : {duplicate_dates}")
    print(f"Invalid max temp    : {invalid_max_temp}")
    print(f"Invalid min temp    : {invalid_min_temp}")
    print(f"Invalid temp logic  : {invalid_temp_logic}")
    print(f"Negative rainfall   : {negative_rainfall}")

    if (
        null_values == 0
        and duplicate_dates == 0
        and invalid_max_temp == 0
        and invalid_min_temp == 0
        and invalid_temp_logic == 0
        and negative_rainfall == 0
    ):
        print("Status              : PASS")
    else:
        print("Status              : FAIL")

def test_invalid_temperature(df):
    print("\n===== TEST SUHU TIDAK VALID =====")

    # Membuat salinan data asli khusus untuk testing
    test_df = df.copy()

    # Sengaja membuat suhu maksimal tidak valid
    test_df.loc[0, "suhu_maksimal_c"] = 100

    print("Suhu maksimal pada data test diubah menjadi 100°C")

    try:
        # Hanya melakukan validation
        # TIDAK melakukan load ke BigQuery
        validate_data(test_df)

        print("❌ TEST GAGAL: Data tidak valid lolos!")

    except Exception as e:
        print("✅ TEST BERHASIL: Data ditolak!")
        print(f"Alasan: {e}")

    #Test NULL
def test_null_value(df):
    print("\n===== TEST NULL VALUE =====")
    # Membuat salinan data asli
    test_df = df.copy()
    # Sengaja membuat nilai suhu menjadi NULL
    test_df.loc[0, "suhu_maksimal_c"] = None
    print("Suhu maksimal pada data test diubah menjadi NULL")
    try:
        # Hanya melakukan validation
        validate_data(test_df)

        print("❌ TEST GAGAL: Data NULL lolos!")
    except Exception as e:
        print("✅ TEST BERHASIL: Data NULL ditolak!")
        print(f"Alasan: {e}")
        
#Test Duplicate date
def test_duplicate_date(df):
    print("\n===== TEST DUPLICATE DATE =====")
    # Membuat salinan data asli
    test_df = df.copy()
    # Membuat tanggal pertama duplikat
    test_df.loc[1, "tanggal"] = test_df.loc[0, "tanggal"]
    print("Tanggal pada baris ke-2 dibuat sama dengan baris pertama")
    try:
        # Hanya melakukan validation
        validate_data(test_df)
        print("❌ TEST GAGAL: Data duplikat lolos!")
    except Exception as e:
        print("✅ TEST BERHASIL: Data duplikat ditolak!")
        print(f"Alasan: {e}")
#Test Suhu Minimum > Maksimum
def test_invalid_temperature_logic(df):
    print("\n===== TEST LOGIKA SUHU =====")
    # Membuat salinan data asli
    test_df =df.copy()
    # Membuat suhu minimal lebih besar dari suhu maksimal
    test_df.loc[0, "suhu_minimal_c"] = 35
    test_df.loc[0, "suhu_maksimal_c"] = 30
    print("suhu minimal dibuat 35°C")
    print("Suhu maksimal dibuat 30°C")
    try:
        validate_data(test_df)
        print("❌ TEST GAGAL: Data dengan logika suhu yang salah lolos!")
    except Exception as e:
        print("✅ TEST BERHASIL: Data ditolak!")
        print(f"Alasan: {e}")
# Test Curah Hujan Negatif
def test_negative_rainfall(df):
    print("\n===== TEST CURAH HUJAN NEGATIF =====")
    # Membuat salinan data asli
    test_df = df.copy()
    # Sengaja membuat curah hujan menjadi negatif
    test_df.loc[0, "total_hujan_mm"] = -5
    print("Total hujan pada data test diubah menjadi -5 mm")
    try:
        # Hanya melakukan validation
        validate_data(test_df)
        print("❌ TEST GAGAL: Data curah hujan negatif lolos!")
    except Exception as e:
        print("✅ TEST BERHASIL: Data ditolak!")
        print(f"Alasan: {e}")
    #  Pastikan Data Invalid Tidak Masuk BigQuery
def test_pipeline_reject_invalid_data(df):
    print("\n===== TEST PIPELINE INVALID DATA =====")

    test_df = df.copy()

    # Sengaja membuat data tidak valid
    test_df.loc[0, "suhu_maksimal_c"] = 100

    print("Data test memiliki suhu maksimal = 100°C")

    # Validation
    validate_data(test_df)

    # Baris ini hanya akan dijalankan jika validation berhasil
    print("Data lolos validation, siap di-load ke BigQuery.")           
# ==========================================
# 3. LOAD
# ==========================================
def load_to_bigquery(df):
    print("Mengunggah data ke BigQuery secara incremental...")
    client = bigquery.Client(project=PROJECT_ID)
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    # Cek tanggal yang sudah ada di BigQuery
    query = f"""
        SELECT tanggal
        FROM `{table_ref}`
    """
    existing_data = client.query(query).to_dataframe()
    # Jika tabel sudah memiliki data
    if not existing_data.empty:
        # Pastikan format tanggal sama
        existing_dates = set(
            pd.to_datetime(existing_data["tanggal"]).dt.date
        )
        # Hanya ambil data yang belum ada
        df_new = df[
            ~df["tanggal"].dt.date.isin(existing_dates)
        ].copy()
    else:
        # Jika tabel masih kosong, semua data dianggap baru
        df_new = df.copy()
    # Tidak ada data baru
    if df_new.empty:
        print("Tidak ada data baru untuk dimasukkan.")
        return
    print(f"Data baru yang akan dimasukkan: {len(df_new)} baris")
    # Tambahkan data baru
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_APPEND")
    job = client.load_table_from_dataframe(
        df_new,
        table_ref,
        job_config=job_config)
    job.result()
    print(
        f"Berhasil menambahkan {len(df_new)} baris "
        f"ke {table_ref}")

#fungsi analytics
def get_weather_analytics():
    print("\n===== WEATHER ANALYTICS =====")
    client = bigquery.Client(project=PROJECT_ID)
    query = f"""
        SELECT
            bulan,
            jumlah_hari,
            rata_suhu_maksimal_c,
            rata_suhu_minimal_c,
            suhu_tertinggi_c,
            suhu_terendah_c,
            total_hujan_mm
        FROM `{PROJECT_ID}.{DATASET_ID}.monthly_weather_analytics`
        ORDER BY bulan
    """
    df_analytics = client.query(query).to_dataframe()
    print(df_analytics.to_string(index=False))
    return df_analytics
# ==========================================
# MENJALANKAN ETL PIPELINE
# ==========================================
if __name__ == "__main__":
    try:
        # EXTRACT
        data_mentah = extract_data()
        # TRANSFORM
        data_bersih = transform_data(data_mentah)
        # Preview
        print("\n===== PREVIEW DATA =====")
        print(data_bersih.head())
        print("\n===== INFORMASI DATA =====")
        print(data_bersih.info())
        # Data Quality Check
        validate_data(data_bersih)
        # Data Quality Report
        generate_quality_report(data_bersih)
        #Test suhu tidak valid
        test_invalid_temperature(data_bersih)
        #Test NULL
        test_null_value(data_bersih)  
        #Test Duplicate date
        test_duplicate_date(data_bersih)
        #Test logika suhu
        test_invalid_temperature_logic(data_bersih)
        # Test curah hujan negatif
        test_negative_rainfall(data_bersih)
        # Pastikan Data Invalid Tidak Masuk BigQuery
        # test_pipeline_reject_invalid_data(data_bersih)
        # LOAD
        load_to_bigquery(data_bersih)
        # Analytics
        get_weather_analytics()
        print("\nPipeline ETL selesai dengan sukses!")
    except Exception as e:
        print(f"\nTerjadi kesalahan pada pipeline:")
        print(e)