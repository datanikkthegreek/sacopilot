from .core import create_app
from .router import router
from .routes import agent as agent_routes
from .routes import mail as mail_routes
from .routes import meetings as meetings_routes
from .routes import usecases as usecases_routes

app = create_app(routers=[
    router,
    mail_routes.router,
    agent_routes.router,
    meetings_routes.router,
    usecases_routes.router,
])
