"""Database models and persistence layer using SQLite and SQLAlchemy."""

from datetime import datetime, timedelta
import json
import os
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.models import DiscoveredOffer, OfferState, StateDiff
from app.utils.logger import logger

Base = declarative_base()


class OfferModel(Base):
    """Table to record known offers."""

    __tablename__ = "offers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    offer_id = Column(String(50), unique=True, index=True, nullable=False)
    curso = Column(String(255), nullable=False)
    unidade = Column(String(255), nullable=False)
    turno = Column(String(100), nullable=False)
    url = Column(Text, nullable=False)
    first_detected_at = Column(DateTime, default=datetime.now, nullable=False)
    last_checked_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    last_state_json = Column(Text, nullable=True)
    last_state_hash = Column(String(64), nullable=True)


class CheckModel(Base):
    """Table to record execution history and verification results."""

    __tablename__ = "checks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    offer_id = Column(String(50), index=True, nullable=False)
    checked_at = Column(DateTime, default=datetime.now, nullable=False)
    is_success = Column(Boolean, default=True, nullable=False)
    status_code = Column(Integer, default=200, nullable=False)
    state_json = Column(Text, nullable=True)
    diff_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)


class AlertModel(Base):
    """Table to record sent alerts for deduplication and auditing."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_type = Column(String(50), index=True, nullable=False)
    offer_id = Column(String(50), index=True, nullable=True)
    state_hash = Column(String(64), index=True, nullable=True)
    channel = Column(String(50), default="telegram", nullable=False)
    sent_at = Column(DateTime, default=datetime.now, nullable=False)
    message_content = Column(Text, nullable=False)


class SettingModel(Base):
    """Table to record dynamic key-value configuration settings."""

    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


class Database:
    """Encapsulates SQLite database operations."""

    def __init__(self, database_url: str = "sqlite:///data/senac_monitor.db"):
        # Ensure directory exists for sqlite file
        if database_url.startswith("sqlite:///"):
            file_path = database_url.replace("sqlite:///", "")
            dir_path = os.path.dirname(file_path)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)

        self.engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.init_db()

    def init_db(self) -> None:
        """Creates tables if they do not exist."""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Banco de dados SQLite inicializado com sucesso.")

    def get_session(self) -> Session:
        """Yields a new database session."""
        return self.SessionLocal()

    def get_offer(self, offer_id: str) -> Optional[OfferModel]:
        """Retrieves offer record by offer ID."""
        with self.get_session() as session:
            stmt = select(OfferModel).where(OfferModel.offer_id == offer_id)
            return session.execute(stmt).scalar_one_or_none()

    def get_last_state(self, offer_id: str) -> Optional[OfferState]:
        """Retrieves last recorded OfferState for an offer ID."""
        with self.get_session() as session:
            stmt = select(OfferModel).where(OfferModel.offer_id == offer_id)
            offer = session.execute(stmt).scalar_one_or_none()
            if offer and offer.last_state_json:
                try:
                    data = json.loads(offer.last_state_json)
                    return OfferState(**data)
                except Exception as err:
                    logger.error(f"Erro ao deserializar last_state_json da oferta {offer_id}: {err}")
            return None

    def upsert_offer(
        self,
        offer_id: str,
        curso: str,
        unidade: str,
        turno: str,
        url: str,
        state: Optional[OfferState] = None,
    ) -> OfferModel:
        """Inserts or updates an offer in the database."""
        with self.get_session() as session:
            stmt = select(OfferModel).where(OfferModel.offer_id == offer_id)
            existing = session.execute(stmt).scalar_one_or_none()
            now = datetime.now()

            state_json = json.dumps(state.model_dump(mode="json"), ensure_ascii=False) if state else None
            state_hash = state.compute_state_hash() if state else None

            if existing:
                existing.curso = curso
                existing.unidade = unidade
                existing.turno = turno
                existing.url = url
                existing.last_checked_at = now
                if state:
                    existing.last_state_json = state_json
                    existing.last_state_hash = state_hash
                session.commit()
                session.refresh(existing)
                return existing
            else:
                new_offer = OfferModel(
                    offer_id=offer_id,
                    curso=curso,
                    unidade=unidade,
                    turno=turno,
                    url=url,
                    first_detected_at=now,
                    last_checked_at=now,
                    last_state_json=state_json,
                    last_state_hash=state_hash,
                )
                session.add(new_offer)
                session.commit()
                session.refresh(new_offer)
                return new_offer

    def record_check(
        self,
        offer_id: str,
        is_success: bool,
        status_code: int = 200,
        state: Optional[OfferState] = None,
        diff: Optional[StateDiff] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Records a check verification entry in history."""
        with self.get_session() as session:
            check = CheckModel(
                offer_id=offer_id,
                checked_at=datetime.now(),
                is_success=is_success,
                status_code=status_code,
                state_json=json.dumps(state.model_dump(mode="json"), ensure_ascii=False) if state else None,
                diff_json=json.dumps(diff.model_dump(mode="json"), default=str, ensure_ascii=False) if diff else None,
                error_message=error_message,
            )
            session.add(check)
            session.commit()

    def is_duplicate_alert(
        self,
        alert_type: str,
        offer_id: Optional[str],
        state_hash: Optional[str],
        channel: str = "telegram",
        cooldown_hours: int = 12,
    ) -> bool:
        """Verifies if an identical alert was already sent within cooldown window."""
        with self.get_session() as session:
            cutoff = datetime.now() - timedelta(hours=cooldown_hours)
            query = select(AlertModel).where(
                AlertModel.alert_type == alert_type,
                AlertModel.channel == channel,
                AlertModel.sent_at >= cutoff,
            )
            if offer_id:
                query = query.where(AlertModel.offer_id == offer_id)
            if state_hash:
                query = query.where(AlertModel.state_hash == state_hash)

            found = session.execute(query).scalar_one_or_none()
            return found is not None

    def record_alert(
        self,
        alert_type: str,
        offer_id: Optional[str],
        state_hash: Optional[str],
        message_content: str,
        channel: str = "telegram",
    ) -> None:
        """Records an alert dispatch to avoid duplicate triggers."""
        with self.get_session() as session:
            alert = AlertModel(
                alert_type=alert_type,
                offer_id=offer_id,
                state_hash=state_hash,
                channel=channel,
                sent_at=datetime.now(),
                message_content=message_content,
            )
            session.add(alert)
            session.commit()

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Gets runtime setting value."""
        with self.get_session() as session:
            setting = session.get(SettingModel, key)
            return setting.value if setting else default

    def set_setting(self, key: str, value: str) -> None:
        """Sets runtime setting value."""
        with self.get_session() as session:
            setting = session.get(SettingModel, key)
            if setting:
                setting.value = value
                setting.updated_at = datetime.now()
            else:
                setting = SettingModel(key=key, value=value, updated_at=datetime.now())
                session.add(setting)
            session.commit()

    def get_all_offers(self) -> List[OfferModel]:
        """Returns all registered offers."""
        with self.get_session() as session:
            return list(session.execute(select(OfferModel)).scalars().all())

    def get_last_check(self, offer_id: str) -> Optional[CheckModel]:
        """Returns the most recent check record for an offer ID."""
        with self.get_session() as session:
            stmt = (
                select(CheckModel)
                .where(CheckModel.offer_id == offer_id)
                .order_by(CheckModel.checked_at.desc())
                .limit(1)
            )
            return session.execute(stmt).scalar_one_or_none()
