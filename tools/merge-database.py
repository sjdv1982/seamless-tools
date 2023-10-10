import sqlite3

def merge_databases(db1, db2):
    con3 = sqlite3.connect(db1)

    con3.execute("ATTACH '" + db2 +  "' as db2")

    con3.execute("BEGIN")
    for table in con3.execute("SELECT * FROM db2.sqlite_master WHERE type='table'"):
        print("TABLE", table[1])

        combine=f"""INSERT or IGNORE INTO {table[1]} SELECT * FROM db2.{table[1]}"""    
        con3.execute(combine)
    con3.commit()
    con3.execute("detach database db2")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=argparse.FileType(), help="Seamless database to take data from", required=True)
    parser.add_argument("--dest", type=argparse.FileType(), help="Seamless database to add data to", required=True)
    args = parser.parse_args()

    merge_databases(args.dest.name, args.source.name)

