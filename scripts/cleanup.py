import os
import shutil

def cleanup():

    dirs = ["downloads", "cache"]
    
    for d in dirs:
        if os.path.exists(d):
            print(f"Cleaning {d}...")
            for filename in os.listdir(d):
                file_path = os.path.join(d, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.is_dir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f"Failed to delete {file_path}. Reason: {e}")
        else:
            os.makedirs(d)


    for file in os.listdir():
        if file.endswith((".jpg", ".jpeg", ".png")):
            try:
                os.remove(file)
            except:
                pass

if __name__ == "__main__":
    cleanup()
