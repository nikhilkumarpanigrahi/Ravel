"""GSQL schema, loading jobs, and bounded investigation queries for TigerGraph (Savanna/CE).

Written defensively (explicit accumulators, scalar anchors passed from the adapter) so queries
install cleanly on first connection. Verified against the live instance when credentials bind.
"""

from __future__ import annotations

SCHEMA_GSQL = r"""
USE GRAPH @@graphname@@

CREATE VERTEX Customer(PRIMARY_ID customer_id STRING, card_label STRING, card1 STRING,
    card6 STRING, home_region STRING) WITH primary_id_as_attribute="true"
CREATE VERTEX Card(PRIMARY_ID card_id STRING, customer_id STRING, card1 STRING,
    card6 STRING, network STRING) WITH primary_id_as_attribute="true"
CREATE VERTEX Transaction(PRIMARY_ID txn_id STRING, ts DATETIME, amount DOUBLE,
    product_cd STRING, channel STRING, risk_score DOUBLE, customer_id STRING,
    card_id STRING, addr1 STRING, addr2 STRING, p_email STRING, device_id STRING,
    email_conflict BOOL) WITH primary_id_as_attribute="true"
CREATE VERTEX DeviceProfile(PRIMARY_ID device_id STRING, dev_profile STRING, device_type STRING,
    os STRING, browser STRING, screen STRING) WITH primary_id_as_attribute="true"
CREATE VERTEX EmailDomain(PRIMARY_ID email_domain STRING) WITH primary_id_as_attribute="true"
CREATE VERTEX BillingRegion(PRIMARY_ID region_id STRING) WITH primary_id_as_attribute="true"
CREATE VERTEX ClosedCase(PRIMARY_ID case_id STRING, customer_id STRING, card_id STRING,
    opened_at DATETIME, closed_at DATETIME, outcome STRING, pattern STRING,
    first_fraud_txn_id STRING, n_txns INT, exposure_usd DOUBLE, connected_card_ids STRING,
    actions_taken STRING, report_filed STRING, summary STRING) WITH primary_id_as_attribute="true"
CREATE VERTEX FraudCase(PRIMARY_ID graph_case_id STRING, case_id STRING, customer_id STRING,
    verdict STRING, pattern STRING, exposure_usd DOUBLE, summary STRING,
    created_at DATETIME) WITH primary_id_as_attribute="true"

CREATE DIRECTED EDGE OWNS(FROM Customer, TO Card)
CREATE DIRECTED EDGE MADE_BY(FROM Transaction, TO Card)
CREATE DIRECTED EDGE CARD_OF(FROM Transaction, TO Customer)
CREATE DIRECTED EDGE FROM_DEVICE(FROM Transaction, TO DeviceProfile)
CREATE DIRECTED EDGE PURCHASER_EMAIL(FROM Transaction, TO EmailDomain)
CREATE DIRECTED EDGE BILLED_IN(FROM Transaction, TO BillingRegion)
CREATE DIRECTED EDGE NEXT(FROM Transaction, TO Transaction, secs DOUBLE)
CREATE DIRECTED EDGE INVOLVES(FROM ClosedCase, TO Transaction)
CREATE DIRECTED EDGE ON_CARD(FROM ClosedCase, TO Card)
CREATE DIRECTED EDGE CONNECTED_TO(FROM ClosedCase, TO Card)
CREATE DIRECTED EDGE RESULTED_IN(FROM FraudCase, TO Card)
CREATE DIRECTED EDGE INVOLVES_FRAUD(FROM FraudCase, TO Transaction)

CREATE GRAPH @@graphname@@(Customer, Card, Transaction, DeviceProfile, EmailDomain,
    BillingRegion, ClosedCase, FraudCase, OWNS, MADE_BY, CARD_OF, FROM_DEVICE,
    PURCHASER_EMAIL, BILLED_IN, NEXT, INVOLVES, ON_CARD, CONNECTED_TO, RESULTED_IN,
    INVOLVES_FRAUD)
"""

LOAD_JOBS_GSQL = r"""
USE GRAPH @@graphname@@

CREATE LOADING JOB load_ravel FOR GRAPH @@graphname@@ {
    DEFINE FILENAME f_customer;
    DEFINE FILENAME f_card;
    DEFINE FILENAME f_txn;
    DEFINE FILENAME f_device;
    DEFINE FILENAME f_email;
    DEFINE FILENAME f_region;
    DEFINE FILENAME f_closed;
    DEFINE FILENAME f_closed_txn;
    DEFINE FILENAME f_next;

    LOAD f_customer TO VERTEX Customer VALUES($0, $1, $2, $3, $4) USING header="true", separator=",";
    LOAD f_card TO VERTEX Card VALUES($0, $1, $2, $3, $4) USING header="true", separator=",";
    LOAD f_card TO EDGE OWNS VALUES($1, $0) USING header="true", separator=",";
    LOAD f_txn TO VERTEX Transaction VALUES($0, ToDateTime($2), $3, $4, $5, $6, $7, $8, $11, $12, $13, $16,
        $21 == "1") USING header="true", separator=",";
    LOAD f_txn TO EDGE MADE_BY VALUES($0, $8) USING header="true", separator=",";
    LOAD f_txn TO EDGE CARD_OF VALUES($0, $7) USING header="true", separator=",";
    LOAD f_txn TO EDGE FROM_DEVICE VALUES($0, $16) USING header="true", separator=",";
    LOAD f_txn TO EDGE PURCHASER_EMAIL VALUES($0, $13) USING header="true", separator=",";
    LOAD f_txn TO EDGE BILLED_IN VALUES($0, $11) USING header="true", separator=",";
    LOAD f_device TO VERTEX DeviceProfile VALUES($0, $1, $2, $3, $4, $5) USING header="true", separator=",";
    LOAD f_email TO VERTEX EmailDomain VALUES($0) USING header="true", separator=",";
    LOAD f_region TO VERTEX BillingRegion VALUES($0) USING header="true", separator=",";
    LOAD f_closed TO VERTEX ClosedCase VALUES($0, $1, $2, ToDateTime($3), ToDateTime($4), $5, $6, $7, $8,
        $9, $10, $12, $13, $14) USING header="true", separator=",";
    LOAD f_closed_txn TO EDGE INVOLVES VALUES($0, $1) USING header="true", separator=",";
    LOAD f_closed TO EDGE ON_CARD VALUES($0, $2) USING header="true", separator=",";
    LOAD f_next TO EDGE NEXT VALUES($0, $1, $3) USING header="true", separator=",";
}
"""

QUERIES_GSQL = r"""
USE GRAPH @@graphname@@

# get_txn: one transaction with full attributes
CREATE QUERY get_txn(STRING txn_id) FOR GRAPH @@graphname@@ SYNTAX v2 {
    T = {Transaction.*};
    T = SELECT s FROM T:s WHERE s.txn_id == txn_id;
    results = SELECT s FROM T:s RETURN s;
    PRETTY_PRINT results;
}

# card_history: recent transactions of a card, newest first
CREATE QUERY card_history(STRING customer_id, INT limit) FOR GRAPH @@graphname@@ SYNTAX v2 {
    T = {Transaction.*};
    T = SELECT s FROM T:s WHERE s.customer_id == customer_id
        ORDER BY s.ts DESC LIMIT limit;
    results = SELECT s FROM T:s RETURN s;
    PRETTY_PRINT results;
}

# card_window: transactions on a card in the N hours before anchor_ts
CREATE QUERY card_window(STRING customer_id, DATETIME anchor_ts, INT hours, INT limit)
FOR GRAPH @@graphname@@ SYNTAX v2 {
    T = {Transaction.*};
    T = SELECT s FROM T:s
        WHERE s.customer_id == customer_id AND s.ts >= datetime_add(anchor_ts, -hours, "HOUR") AND s.ts <= anchor_ts
        ORDER BY s.ts ASC LIMIT limit;
    results = SELECT s FROM T:s RETURN s;
    PRETTY_PRINT results;
}

# shared_devices: other customers whose cards used the SAME device profile
CREATE QUERY shared_devices(STRING customer_id, INT limit) FOR GRAPH @@graphname@@ SYNTAX v2 {
    SetAccum<STRING> @@mydev;
    SumAccum<INT> @cnt;
    T = {Transaction.*};
    T = SELECT t FROM T:t WHERE t.customer_id == customer_id AND t.device_id != ""
        ACCUM @@mydev += t.device_id;
    T2 = {Transaction.*};
    T2 = SELECT t FROM T2:t
        WHERE t.device_id IN @@mydev AND t.customer_id != customer_id
        ACCUM t.@cnt += 1
        ORDER BY t.@cnt DESC LIMIT limit;
    results = SELECT t FROM T2:t RETURN t, t.@cnt AS shared_txns;
    PRETTY_PRINT results;
}

# shared_regions: other customers active in the same billing regions
CREATE QUERY shared_regions(STRING customer_id, INT limit) FOR GRAPH @@graphname@@ SYNTAX v2 {
    SetAccum<STRING> @@myreg;
    SumAccum<INT> @cnt;
    T = {Transaction.*};
    T = SELECT t FROM T:t WHERE t.customer_id == customer_id AND t.addr1 != ""
        ACCUM @@myreg += t.addr1;
    T2 = {Transaction.*};
    T2 = SELECT t FROM T2:t
        WHERE t.addr1 IN @@myreg AND t.customer_id != customer_id
        ACCUM t.@cnt += 1
        ORDER BY t.@cnt DESC LIMIT limit;
    results = SELECT t FROM T2:t RETURN t;
    PRETTY_PRINT results;
}

# related_transactions: recent activity from devices shared with this customer
CREATE QUERY related_transactions(STRING customer_id, DATETIME from_ts, INT limit)
FOR GRAPH @@graphname@@ SYNTAX v2 {
    SetAccum<STRING> @@mydev;
    T = {Transaction.*};
    T = SELECT t FROM T:t WHERE t.customer_id == customer_id AND t.device_id != ""
        ACCUM @@mydev += t.device_id;
    T2 = {Transaction.*};
    T2 = SELECT t FROM T2:t
        WHERE t.device_id IN @@mydev AND t.customer_id != customer_id AND t.ts >= from_ts
        ORDER BY t.ts DESC LIMIT limit;
    results = SELECT t FROM T2:t RETURN t;
    PRETTY_PRINT results;
}

# historical_cases: closed-case memory, filterable
CREATE QUERY historical_cases(STRING customer_id, STRING outcome, STRING pattern, INT limit)
FOR GRAPH @@graphname@@ SYNTAX v2 {
    C = {ClosedCase.*};
    C = SELECT s FROM C:s
        WHERE (customer_id == "" OR s.customer_id == customer_id)
          AND (outcome == "" OR s.outcome == outcome)
          AND (pattern == "" OR s.pattern == pattern)
        ORDER BY s.closed_at DESC LIMIT limit;
    results = SELECT s FROM C:s RETURN s;
    PRETTY_PRINT results;
}

# high_degree_count: bind degree for an entity id (customer or device)
CREATE QUERY degree_of(STRING entity_id, INT kind) FOR GRAPH @@graphname@@ SYNTAX v2 {
    SumAccum<INT> @n;
    IF kind == 0 THEN
        T = {Transaction.*};
        T = SELECT t FROM T:t WHERE t.customer_id == entity_id ACCUM @@deg += 1;
    ELSE
        T = {Transaction.*};
        T = SELECT t FROM T:t WHERE t.device_id == entity_id ACCUM @@deg += 1;
    END;
    PRINT @@deg;
}

# connected_entities: devices/regions/emails used by this customer, with counts
CREATE QUERY connected_entities(STRING customer_id, INT limit) FOR GRAPH @@graphname@@ SYNTAX v2 {
    SumAccum<INT> @dev_n;
    T = {Transaction.*};
    T = SELECT t FROM T:t WHERE t.customer_id == customer_id
        ACCUM @@devs += t.device_id, @@regions += t.addr1, @@emails += t.p_email;
    PRINT customer_id, @@devs, @@regions, @@emails;
}

# write_fraud_case: persist a completed case into the graph (case memory)
CREATE QUERY write_fraud_case(
    STRING graph_case_id, STRING case_id, STRING customer_id, STRING verdict,
    STRING pattern, DOUBLE exposure_usd, STRING summary,
    SET<STRING> card_ids, SET<STRING> txn_ids) FOR GRAPH @@graphname@@ SYNTAX v2 {
    F = {FraudCase.*};
    INSERT INTO FraudCase VALUES (graph_case_id, case_id, customer_id, verdict, pattern,
        exposure_usd, summary, now());
    C = {Card.*};
    C = SELECT c FROM C:c WHERE c.card_id IN card_ids
        ACCUM INSERT INTO RESULTED_IN VALUES (graph_case_id, c);
    T = {Transaction.*};
    T = SELECT t FROM T:t WHERE t.txn_id IN txn_ids
        ACCUM INSERT INTO INVOLVES_FRAUD VALUES (graph_case_id, t);
}
"""
