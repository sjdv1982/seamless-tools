import sqlite3

def clear_database(db):
    con = sqlite3.connect(db)

    con.execute("BEGIN")
    for table in con.execute("SELECT * FROM sqlite_schema WHERE type='table'"):
        print("TABLE", table[1])

        cmd=f"""DELETE FROM {table[1]}"""    
        con.execute(cmd)
    con.commit()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("db", type=argparse.FileType(), help="Seamless database to clear")
    args = parser.parse_args()

    clear_database(args.db.name)

