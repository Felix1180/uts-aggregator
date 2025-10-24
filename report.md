# Laporan Teknis: Analisis Log Aggregator Berdasarkan Prinsip Tanenbaum

**Nama Proyek:** UTS-AGGREGATOR  
**Penulis:** Christian Felix - 11221080  
**Tanggal:** 24 Oktober 2025  
**Referensi Utama:**  
Tanenbaum, A. S., & Van Steen, M. (2023). _Distributed Systems: Principles and Paradigms_ (4th ed.). Maarten van Steen.

---

## 1. Ringkasan Sistem dan Arsitektur

### 1.1 Deskripsi Umum

**UTS-AGGREGATOR** adalah sistem log aggregator terdistribusi berbasis _Publish–Subscribe (Pub/Sub)_, dirancang untuk mengumpulkan, memproses, dan mendeduplikasi log dari banyak produsen secara paralel.  
Sistem ini mengutamakan **scalability**, **reliability**, dan **low latency**, sejalan dengan prinsip Tanenbaum dan Van Steen (2023).

**Fitur utama:**

- Mekanisme _At-Least-Once delivery_ untuk mencegah kehilangan data.
- _Idempotent consumer_ menjaga state akhir tetap konsisten meski ada duplikasi.
- _Deduplication store_ berbasis SQLite untuk persistensi dan deteksi duplikasi.
- _Partial ordering_ untuk efisiensi throughput.
- _Retry mechanism_ dengan _exponential backoff_.

---

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

## 2. Bagian Teori (40%)

### T1 (Bab 1): Karakteristik Sistem Terdistribusi dan Trade-Off Pub/Sub

**Distributed systems** terdiri dari komputer independen yang berkoordinasi via _message passing_, menyajikan _single-system image_ dan _resource sharing_ (Bab 1).  
Karakteristik relevan: _scalability_, _openness_, _dependability_.  
Middleware **Pub/Sub** menyembunyikan kompleksitas melalui _access_ dan _location transparency_.

**Trade-off utama:**

- _Distribution transparency_ vs _performance_  
  → Sistem log cepat cenderung mengorbankan transparansi demi _throughput_ dan _low latency_.
- _Failure transparency_ sulit dijamin; _partial failures_ memerlukan aplikasi menangani _retry_ dan _deduplication_.

---

### T2 (Bab 2): Client-Server vs Publish-Subscribe

**Client/Server (C/S)** menggunakan _synchronous request/reply_, menghasilkan _tight coupling_ temporal dan spasial — sulit _scalable_ untuk _log aggregator_ besar (Bab 2).  
Sebaliknya, **Pub/Sub** adalah arsitektur _decentralized_ dan _asynchronous_ dengan _temporal_ dan _spatial decoupling_.

- Publisher mengirim ke _topic_ tanpa mengetahui _subscriber_.
- Broker menyimpan pesan secara _durable_.
- Mendukung _high throughput_ dan _availability_.
- Dapat menambah produsen/konsumen tanpa _downtime_.

---

### T3 (Bab 3): At-Least-Once vs Exactly-Once & Idempotent Consumer

_Delivery semantics_ menentukan _reliability_ (Bab 8):

| Jenis Semantik | Karakteristik                 | Risiko                     |
| -------------- | ----------------------------- | -------------------------- |
| At-Most-Once   | Pesan dikirim maksimal sekali | Data hilang                |
| At-Least-Once  | Pesan dikirim minimal sekali  | Duplikasi                  |
| Exactly-Once   | Pesan dikirim tepat sekali    | Overhead koordinasi tinggi |

Karena sistem log aggregator mengadopsi **At-Least-Once**, maka **idempotent consumer** sangat penting:  
menjalankan operasi berulang harus menghasilkan _state_ akhir yang sama, untuk mencegah log duplikat.

---

### T4 (Bab 4): Skema Penamaan Topic dan Event_ID

- **Topic**: menggunakan _structured naming_ (misal: `domain.service.log_type`).
- **Event_ID**: harus unik dan _collision-resistant_ (misal **UUIDv4** sebagai _pure name_) (Bab 6).

**Deduplication** efektif bila `event_id` unik.  
Kolisi menyebabkan _false drop_. Kombinasi **idempotent consumer** + **dedup store** menjamin log hanya diproses satu kali dan menjaga integritas data.

---

### T5 (Bab 5): Ordering

- **Total ordering** → mahal dan menambah _latency_.
- **Partial ordering (FIFO per partition)** → cukup untuk _causal consistency_.

Pendekatan praktis:

- _Logical clocks_ atau _event timestamp_ + _monotonic counter_.

**Batasan:** timestamp fisik tidak selalu _monotonic_ antar node.  
Namun, _partial ordering_ menjaga _throughput_ tanpa memerlukan koordinasi global.

---

### T6 (Bab 6): Failure Modes & Mitigasi

**Failure utama (Bab 8):**

| Jenis Kegagalan | Penyebab                 | Mitigasi                                 |
| --------------- | ------------------------ | ---------------------------------------- |
| Duplikasi       | Retry pada At-Least-Once | Durable dedup store, idempotent consumer |
| Out-of-Order    | Network delay            | FIFO partition                           |
| Crash           | Fail-silent / fail-stop  | Retry dengan exponential backoff         |

Strategi ini menjaga integritas data dan _high availability_ meskipun terjadi _partial failure_.

---

### T7 (Bab 7): Eventual Consistency & Peran Idempotency + Dedup

**Eventual Consistency (EC):**  
Jika tidak ada update baru, semua replika akan _converge_ ke _state_ yang sama (Bab 7).

Kombinasi **idempotency** + **deduplication** memungkinkan konsumer:

- Mengabaikan duplikasi
- Memperbarui _state_ hanya sekali

Hasilnya: EC tercapai secara aman dan _predictable_.

---

### T8 (Bab 1–7): Metrik Evaluasi Sistem

| Metrik             | Definisi                    | Kaitannya ke Desain                                                       |
| ------------------ | --------------------------- | ------------------------------------------------------------------------- |
| **Throughput**     | Log diterima per unit waktu | Partial ordering + Pub/Sub parallel partition mendukung _high throughput_ |
| **Latency**        | Waktu publikasi → konsumsi  | EC + async decoupling menurunkan _latency_, mengorbankan total ordering   |
| **Duplicate Rate** | Persentase event duplikat   | At-Least-Once + dedup store + idempotent consumer menjaga integritas      |

**Trade-off:**  
_Weak consistency_ dan _partial ordering_ meningkatkan _throughput_ & _low latency_,  
sementara _duplicate rate_ dikendalikan oleh deduplication.

---

## 3. Analisis Performa

### Hasil Pengujian Stres

| Metrik               | Nilai    | Interpretasi                         |
| -------------------- | -------- | ------------------------------------ |
| Total event diterima | 4800     | Semua pesan berhasil diterima broker |
| Event unik diproses  | 4000     | 83.3% pesan unik setelah deduplikasi |
| Duplikasi dibuang    | 800      | 16.7% duplikasi berhasil disaring    |
| Duplicate rate       | 0.167    | Wajar untuk At-Least-Once semantics  |
| Latency (estimasi)   | < 100 ms | Efisien berkat Pub/Sub asinkron      |

---

### Analisis:

- **High throughput** dicapai berkat partisi paralel (Bab 1 & 5).
- **Low latency** berkat _asynchronous decoupling_ (Bab 2).
- **Duplicate rate** terkontrol melalui _dedup store_ + _idempotency_ (Bab 3 & 7).

---

## 4. Kesimpulan

Sistem **UTS-AGGREGATOR** berhasil menerapkan prinsip **Tanenbaum (Bab 1–7)** pada arsitektur **Pub/Sub aggregator**:

- Menyeimbangkan _reliability_ dan _performance_.
- _Trade-off_ antara transparansi distribusi dan _weak consistency_ dilakukan secara sadar.
- Kombinasi **At-Least-Once + idempotent consumer + dedup store** menjaga integritas data.
- Metrik (_throughput, latency, duplicate rate_) sejalan dengan keputusan desain.

---

## 5. Daftar Pustaka

- Tanenbaum, A. S., & Van Steen, M. (2023). _Distributed Systems: Principles and Paradigms_ (4th ed.). Maarten van Steen.
- Confluent. (2025, Okt 24). _Publish–Subscribe: Intro to Pub/Sub Messaging._ [https://www.confluent.io/learn/publish-subscribe/](https://www.confluent.io/learn/publish-subscribe/)
- Amazon Web Services. (2025, Okt 24). _What is Pub/Sub Messaging?_ [https://aws.amazon.com/what-is/pub-sub-messaging/](https://aws.amazon.com/what-is/pub-sub-messaging/)
- Ryanov, N. (2025). _Delivery and Processing Semantics: Overview._ [https://nryanov.com/overview/messaging/delivery-semantics/](https://nryanov.com/overview/messaging/delivery-semantics/)
- Lydtech Consulting. (2025). _Kafka Idempotent Consumer & Transactional Outbox._ [https://www.lydtechconsulting.com/blog/kafka-idempotent-consumer-transactional-outbox](https://www.lydtechconsulting.com/blog/kafka-idempotent-consumer-transactional-outbox)
- GeeksforGeeks. (2025). _Causal Consistency Model in System Design._ [https://www.geeksforgeeks.org/system-design/causal-consistency-model-in-system-design/](https://www.geeksforgeeks.org/system-design/causal-consistency-model-in-system-design/)
- Hazelcast. (2025). _Navigating Consistency in Distributed Systems: Choosing the Right Trade-Offs._ [https://hazelcast.com/blog/navigating-consistency-in-distributed-systems-choosing-the-right-trade-offs/](https://hazelcast.com/blog/navigating-consistency-in-distributed-systems-choosing-the-right-trade-offs/)
