import os
from dotenv import load_dotenv
from waterlevel import fetch_process_and_plot
from email_setup import send_alert

load_dotenv()
THRESHOLD = float(os.getenv("THRESHOLD", 200))

def main():
    print("Running water level check and generating plot...")
    try:
        breach_time, breach_value, plot_path = fetch_process_and_plot(THRESHOLD)
        
        if plot_path:
            print(f"Plot saved successfully to {plot_path}")
            
        if breach_time is not None:
            print(f"Threshold exceeded! First occurrence at {breach_time} with {breach_value} cm.")
            send_alert(breach_time, breach_value, plot_path)
        else:
            print("Levels remain below threshold. No email sent.")
            
    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    main()