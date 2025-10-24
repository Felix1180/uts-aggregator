# Laporan Teknis: Analisis Log Aggregator Berdasarkan Prinsip Tanenbaum

**Nama Proyek:** UTS-AGGREGATOR
**Penulis:** —
**Tanggal:** 24 Oktober 2025
**Referensi Utama:** Tanenbaum, A. S., & Van Steen, M. (2017). _Distributed Systems: Principles and Paradigms_ (2nd ed.). Pearson Education.

---

## 1. Ringkasan Sistem dan Arsitektur

### 1.1 Deskripsi Umum

Sistem **UTS-AGGREGATOR** adalah implementasi _log aggregator_ terdistribusi berbasis **Publish–Subscribe (Pub/Sub)** yang dirancang untuk mengumpulkan, memproses, dan mendeduplikasi log dari banyak produsen (publisher) secara paralel. Sistem ini mengutamakan **scalability**, **reliability**, dan **low latency**, sesuai dengan prinsip-prinsip sistem terdistribusi menurut Tanenbaum dan Van Steen (2017).

Fitur utama:

- Mekanisme **At-Least-Once delivery** untuk menjamin _no data loss_.
- **Idempotent consumer** agar state akhir tetap konsisten walau terjadi duplikasi.
- **Deduplication store** berbasis SQLite untuk persistensi dan deteksi duplikasi.
- **Partial ordering** untuk efisiensi throughput.
- **Retry mechanism** dengan _exponential backoff_.

### 1.2 Struktur Direktori Proyek

```
UTS-AGGREGATOR/
│
├── data/
│   ├── dedup.db              # Penyimpanan state deduplikasi
│   ├── dedup.db-shm
│   └── dedup.db-wal
│
├── src/
│   ├── main.py               # Entry point server aggregator
│   ├── publisher_sim.py      # Simulator publisher log
│   ├── dedup_store.py        # Modul deduplikasi event_id
│   ├── models.py             # Definisi struktur data log/event
│   └── __init__.py
│
├── tests/
│   ├── test_dedup.py         # Uji deduplikasi dan idempotensi
│   ├── test_stress_large.py  # Uji performa skala besar
│   ├── test_stress_small.py  # Uji beban kecil
│   ├── test_api_schema_and_stats.py
│   └── test_persistence.py
│
├── docker-compose.yml        # Orkestrasi kontainer aggregator
├── Dockerfile                # Definisi image
├── requirements.txt          # Dependensi Python
├── pytest.ini
└── report.md (dokumen ini)
```

### 1.3 Diagram Arsitektur (ASCII)

```
                +-------------------+
                |   Publisher(s)    |
                |-------------------|
                |  log event + id   |
                +---------+---------+
                          |
                          v
                +-------------------+
                |     Broker PubSub  |
                |-------------------|
                |  queue / topic(s)  |
                +---------+---------+
                          |
                          v
                +-------------------+
                |   Log Aggregator   |
                |-------------------|
                |  - Dedup Store     |
                |  - Retry Handler   |
                |  - Ordering Buffer |
                +---------+---------+
                          |
                          v
                +-------------------+
                |   Consumer (Sink)  |
                |-------------------|
                |  - Idempotent ops  |
                |  - State storage    |
                +-------------------+
```

---

## 2. Keputusan Desain Teknis

### 2.1 Idempotency (Bab 3, 7)

Konsumer dirancang **idempotent** untuk memastikan hasil akhir tetap konsisten meskipun pesan yang sama diterima beberapa kali. Hal ini penting karena sistem menggunakan semantik _At-Least-Once_, sehingga duplikasi akibat _retry_ tidak dapat dihindari (Tanenbaum & Van Steen, 2017, Bab 8).
Contoh implementasi: penyimpanan `event_id` ke dalam _dedup_store_ sebelum memproses log baru.

### 2.2 Deduplication Store (Bab 6)

Dedup store berperan sebagai lapisan penyaring duplikasi berdasarkan `event_id`. Ia memastikan bahwa hanya log unik yang diteruskan ke downstream consumer. Struktur ini menggunakan _collision-resistant identifier_ (UUIDv4), sejalan dengan prinsip _pure naming_ pada Bab 6 (Tanenbaum & Van Steen, 2017).

### 2.3 Ordering (Bab 5)

Sistem menggunakan **Partial Ordering** berbasis _partition FIFO_. Pendekatan ini menjaga urutan kausal antar-log dari produser yang sama tanpa membebani koordinasi global. Sesuai Bab 5, penggunaan jam logis lebih efisien dibandingkan total ordering berbasis jam fisik.

### 2.4 Retry Mechanism (Bab 8)

Retry dilakukan dengan _exponential backoff_ untuk menghindari efek _thundering herd_ (Tanenbaum & Van Steen, 2017). Mekanisme ini juga mencegah overload pada broker atau konsumer ketika sistem sedang melakukan recovery.

---

## 3. Analisis Performa dan Metrik

### 3.1 Hasil Pengujian Stres (file: `test_stress_large.py`)

| Metrik               | Nilai   | Interpretasi                                            |
| -------------------- | ------- | ------------------------------------------------------- |
| Total event diterima | 4800    | Semua pesan dari publisher berhasil diterima broker.    |
| Event unik diproses  | 4000    | 83.3% dari total pesan unik setelah deduplikasi.        |
| Duplikasi dibuang    | 800     | 16.7% duplikasi berhasil disaring oleh dedup store.     |
| Duplicate rate       | 0.167   | Masih dalam batas wajar untuk semantik _At-Least-Once_. |
| Latency (estimasi)   | < 100ms | Menunjukkan efisiensi sistem berbasis Pub/Sub.          |

### 3.2 Analisis

- **Throughput** tinggi dicapai karena sistem menghindari total ordering dan menerapkan partisi paralel (Bab 1 & 5).
- **Latency** rendah karena menggunakan _asynchronous decoupling_ antara publisher dan consumer (Bab 2).
- **Duplicate rate** merupakan konsekuensi semantik _At-Least-Once_ (Bab 3), tetapi terkontrol berkat dedup store.
- Kombinasi **idempotency + deduplication** memastikan _eventual consistency_ tercapai (Bab 7).

---

## 4. Keterkaitan ke Prinsip Tanenbaum (Bab 1–7)

| Bab   | Konsep Utama                             | Penerapan dalam Sistem                                                                   |
| ----- | ---------------------------------------- | ---------------------------------------------------------------------------------------- |
| Bab 1 | _Distribution Transparency, Scalability_ | Pub/Sub digunakan untuk meningkatkan skalabilitas dan mengurangi ketergantungan spasial. |
| Bab 2 | _Client–Server vs Publish–Subscribe_     | Sistem memilih arsitektur Pub/Sub untuk decoupling temporal dan spasial.                 |
| Bab 3 | _Delivery Semantics_                     | Sistem menggunakan _At-Least-Once_ dengan idempotent consumer.                           |
| Bab 4 | _Naming_                                 | `event_id` dihasilkan menggunakan UUIDv4 sebagai _pure name_.                            |
| Bab 5 | _Synchronization & Ordering_             | Menggunakan partial ordering berbasis partition FIFO.                                    |
| Bab 6 | _Fault Tolerance & Failure Handling_     | Dedup store dan retry berperan dalam mekanisme fault-tolerant.                           |
| Bab 7 | _Consistency Models_                     | Sistem mendukung _Eventual Consistency_ melalui deduplication dan idempotency.           |

---

## 5. Kesimpulan

Sistem **UTS-AGGREGATOR** secara efektif menerapkan prinsip-prinsip Tanenbaum (Bab 1–7) dalam konteks arsitektur Pub/Sub. Desain ini menyeimbangkan antara **reliability** dan **performance**, dengan trade-off sadar terhadap transparansi distribusi. Mekanisme _At-Least-Once_ yang dikombinasikan dengan _idempotent consumer_ dan _dedup store_ berhasil menjaga integritas data meskipun terjadi duplikasi akibat retry. Dengan demikian, sistem ini mencapai _high availability_ tanpa mengorbankan _eventual consistency_.

---

## 6. Daftar Pustaka

Tanenbaum, A. S., & Van Steen, M. (2017). _Distributed Systems: Principles and Paradigms_ (2nd ed.). Pearson Education.

Confluent. (2025, Oktober 24). _Publish–Subscribe: Intro to Pub/Sub Messaging_. Diakses dari [https://www.confluent.io/learn/publish-subscribe/](https://www.confluent.io/learn/publish-subscribe/)

Amazon Web Services. (2025, Oktober 24). _What is Pub/Sub Messaging?_. Diakses dari [https://aws.amazon.com/what-is/pub-sub-messaging/](https://aws.amazon.com/what-is/pub-sub-messaging/)

Ryanov, N. (2025). _Delivery and Processing Semantics: Overview_. Diakses dari [https://nryanov.com/overview/messaging/delivery-semantics/](https://nryanov.com/overview/messaging/delivery-semantics/)

Lydtech Consulting. (2025). _Kafka Idempotent Consumer & Transactional Outbox_. Diakses dari [https://www.lydtechconsulting.com/blog/kafka-idempotent-consumer-transactional-outbox](https://www.lydtechconsulting.com/blog/kafka-idempotent-consumer-transactional-outbox)

GeeksforGeeks. (2025). _Causal Consistency Model in System Design_. Diakses dari [https://www.geeksforgeeks.org/system-design/causal-consistency-model-in-system-design/](https://www.geeksforgeeks.org/system-design/causal-consistency-model-in-system-design/)

Hazelcast. (2025). _Navigating Consistency in Distributed Systems: Choosing the Right Trade-Offs_. Diakses dari [https://hazelcast.com/blog/navigating-consistency-in-distributed-systems-choosing-the-right-trade-offs/](https://hazelcast.com/blog/navigating-consistency-in-distributed-systems-choosing-the-right-trade-offs/)