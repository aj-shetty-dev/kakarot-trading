"""
ML Data Pipeline - Collects features and labels for training
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from ..data.models import MLFeatureLog, Symbol
from ..data.database import SessionLocal
from ..config.timezone import ist_now

logger = logging.getLogger(__name__)

class MLDataPipeline:
    """
    Handles logging of technical features and trade outcomes
    to create a dataset for local AI model training.
    """

    def log_features(self, symbol: str, features: Dict[str, Any], signal_type: str, trade_id: Optional[str] = None):
        """
        Log features at the time of a signal.
        """
        db = SessionLocal()
        try:
            # Get symbol ID
            sym_record = db.query(Symbol).filter(Symbol.symbol == symbol).first()
            if not sym_record:
                # Check instrument key
                from ..data.models import SubscribedOption
                opt = db.query(SubscribedOption).filter(SubscribedOption.instrument_key == symbol).first()
                if opt:
                    sym_record = db.query(Symbol).filter(Symbol.symbol == opt.symbol).first()
            
            if not sym_record:
                logger.warning(f"Could not find symbol {symbol} for ML logging")
                return

            log_entry = MLFeatureLog(
                symbol_id=sym_record.id,
                features=features,
                signal_type=signal_type,
                trade_id=trade_id,
                timestamp=ist_now()
            )
            db.add(log_entry)
            db.commit()
            return log_entry.id
        except Exception as e:
            logger.error(f"Error logging ML features: {e}")
            db.rollback()
        finally:
            db.close()

    def update_outcome(self, trade_id: str, pnl_percent: float):
        """
        Update the label for a logged feature set based on trade outcome.
        """
        # Validate if trade_id is a valid UUID string
        import uuid
        try:
            uuid.UUID(str(trade_id))
        except (ValueError, TypeError):
            # If not a valid UUID, we can't query by trade_id in the DB
            # This happens for paper trades that use symbol as ID
            logger.debug(f"Skipping ML outcome update for non-UUID trade_id: {trade_id}")
            return

        db = SessionLocal()
        try:
            log_entry = db.query(MLFeatureLog).filter(MLFeatureLog.trade_id == trade_id).first()
            if log_entry:
                log_entry.pnl_percent = pnl_percent
                log_entry.label = 1 if pnl_percent > 0 else 0
                db.commit()
                logger.info(f"✅ ML Outcome updated for trade {trade_id}: {log_entry.label}")
        except Exception as e:
            logger.error(f"Error updating ML outcome: {e}")
            db.rollback()
        finally:
            db.close()

ml_pipeline = MLDataPipeline()
