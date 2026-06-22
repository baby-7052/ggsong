class Config:
    API_ID: int = 27696582
    API_HASH: str = "45fccefb72a57ff1b858339774b6d005"
    BOT_TOKEN: str = "7928337629:AAEwXvQ5Q4oEzUbKAXoy3McrPPMtrkoAmX4"
    
    TARGET_CHAT_ID: int = -1003863426936
    
    DOWNLOADS_DIR: str = "./downloads"
    CACHE_FILE: str = "./drivers/cache/ffiles.json"
    
    DEFAULT_INTERVAL: int = 10
    MAX_RETRY_ATTEMPTS: int = 2
    
    AUTHORIZED_USERS: list = [7187147313]
    
    MAX_FILE_SIZE_MB: int = 2048
    
    @classmethod
    def validate(cls) -> bool:
        required_fields = [
            cls.API_ID,
            cls.API_HASH,
            cls.BOT_TOKEN,
            cls.TARGET_CHAT_ID,
            cls.AUTHORIZED_USERS
        ]
        return all(required_fields)
