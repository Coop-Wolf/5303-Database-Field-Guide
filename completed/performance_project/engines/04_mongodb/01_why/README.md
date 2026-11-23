# 01 — Why it exists: MongoDB

> **Fixed question:** What problem was this built for, and what does it give up?
>
> **Student artifact:** One paragraph, plus your predictions (below)

## The problem MongoDB solves

Look at how a web application actually uses a purchase. The order page
wants the purchase *with* the product name, the customer's state, and the
card type, all at once. A relational database stores those in four tables
and joins them back together on every request. The application then turns
the joined rows back into one object.

MongoDB's founders (2007, the company behind a busy ad server) asked: what
if the database stored the object the application wants, as one piece?

| | Relational (SQLite, PostgreSQL) | Document (MongoDB) |
| - | ------------------------------- | ------------------ |
| Unit of storage | a row: flat, every column a single value | a **document**: nested fields, lists, sub-documents |
| Shape | fixed by `CREATE TABLE`; every row the same | free: two documents in one collection can differ |
| One purchase, with its details | spread across tables, joined at read time | one document, read in one step |
| Changing the shape | `ALTER TABLE`, sometimes a migration | start writing the new field |
| Spreading data across machines | possible, but bolted on | designed in (sharding, replica sets) |

## The mental model: store what you read

```
SQL:  purchases ─ customers ─ zipcodes ─ states        ┐
                └ products                              ├ joined on every read
                └ cards ─ card_types                    ┘

MongoDB:  purchases: {
            _id: 777777, customer_id: 4021, amount: 19.99, purchase_date: 2025-03-01,
            product_name: "Smart Speaker 65",   ← copied in when the purchase was written
            state_code: "TX",                   ← copied in
            card_type: "visa"                   ← copied in
          }
```

A document is **BSON** (binary JSON) with real types: integers, decimals,
dates, nested objects, arrays. The server is a separate process, `mongod`,
reached over the network like PostgreSQL. You talk to it with commands
(`find`, `aggregate`, `insert`), not SQL text.

## Why that's attractive: four motivations

1. **One read instead of a join.** If a page needs a purchase and its details,
   one document holds them all.
2. **The shape can change.** Add a field to new documents without touching
   old ones. Early in a product, when the data model changes weekly, this
   matters.
3. **Nested data stays nested.** A customer's cards can live *inside* the
   customer as a list, not in a separate table you join back.
4. **Built to spread out.** Replica sets (copies with automatic failover)
   and sharding (splitting a collection across machines) are part of the
   design, not add-ons.

## What it gives up

| Trade-off | Consequence |
| --------- | ----------- |
| **Copies go stale** | A product name copied into a million purchases isn't updated when the product is renamed, unless you update all million. |
| **Nothing enforces references** | A purchase can point at a customer who doesn't exist. MongoDB won't stop it; your code must. |
| **Joins are possible, not natural** | `$lookup` exists, but a design that needs many of them is fighting the engine. |
| **The schema lives in your code** | Without a validator, any document shape is accepted, including typos (`custmer_id`). |
| **No auto-increment** | Numeric ids need a counter document every writer updates, or you use MongoDB's generated `ObjectId`. |
| **Multi-document transactions are the exception** | One document is always atomic; more than one needs a replica set and costs more. |

## Your artifact

1. Write one paragraph: *what MongoDB is for that PostgreSQL isn't, and one
   job where you'd still choose PostgreSQL.*
2. **Predict, before you measure anything.** For each group, will MongoDB
   (indexed, at 1m) be faster, slower, or about the same as PostgreSQL? Keep
   this; [§7](../07_explain/) checks it.

| Queries | What they do | MongoDB vs. PostgreSQL: your prediction |
| ------- | ------------ | ---------------------------------------- |
| Q01, Q02 | fetch one customer; one page of products | |
| Q04 | one customer's 100 most recent purchases | |
| Q09 | revenue by state (a join in SQL; not here) | |
| Q12 | 10 random purchases | |
| Q15 | insert one purchase | |

Then read MongoDB's column of the [concept map](../../../reference/concept_map.md)
and [concept_answers.md](../concept_answers.md).
