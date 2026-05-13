from dotenv import load_dotenv
load_dotenv()  # 這行會把 .env 裡面的變數吃進系統裡
from app import create_app

app = create_app()
if __name__ == "__main__":
    app.run(debug=True)