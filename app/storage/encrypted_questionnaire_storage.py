import json
import snappy

from structlog import get_logger
from jwcrypto.common import base64url_decode

from app.data_model.app_models import QuestionnaireState
from app.storage import data_access
from app.storage.storage_encryption import StorageEncryption

logger = get_logger()


class EncryptedQuestionnaireStorage:

    def __init__(self, user_id, user_ik, pepper, stateless_updates_enabled=False):
        if user_id is None:
            raise ValueError('User id must be set')

        self._user_id = user_id
        self.encrypter = StorageEncryption(user_id, user_ik, pepper)
        self.stateless_updates_enabled = stateless_updates_enabled

    def add_or_update(self, data, version):
        compressed_data = snappy.compress(data)
        encrypted_data = self.encrypter.encrypt_data(compressed_data)

        if self.stateless_updates_enabled:
            logger.debug('saving questionnaire data', user_id=self._user_id)
            questionnaire_state = QuestionnaireState(self._user_id, encrypted_data, version)
        else:
            questionnaire_state = self._find_questionnaire_state()

            if questionnaire_state:
                logger.debug('updating questionnaire data', user_id=self._user_id)
                questionnaire_state.state_data = encrypted_data
                questionnaire_state.version = version
            else:
                logger.debug('creating questionnaire data', user_id=self._user_id)
                questionnaire_state = QuestionnaireState(self._user_id, encrypted_data, version)

        data_access.put(questionnaire_state)

    def get_user_data(self):
        questionnaire_state = self._find_questionnaire_state()
        if questionnaire_state:
            version = questionnaire_state.version or 0

            try:
                # legacy data was stored in a dict, base64-encoded, and not compressed
                data = json.loads(questionnaire_state.state_data)['data']
                is_legacy_data = True
            except ValueError:
                data = questionnaire_state.state_data
                is_legacy_data = False

            decrypted_data = self.encrypter.decrypt_data(data)

            if is_legacy_data:
                decrypted_data = base64url_decode(decrypted_data.decode()).decode()
            else:
                decrypted_data = snappy.uncompress(decrypted_data).decode()

            return decrypted_data, version

        return None, None

    def delete(self):
        logger.debug('deleting users data', user_id=self._user_id)
        questionnaire_state = self._find_questionnaire_state()
        if questionnaire_state:
            data_access.delete(questionnaire_state)

    def _find_questionnaire_state(self):
        logger.debug('getting questionnaire data', user_id=self._user_id)
        return data_access.get_by_key(QuestionnaireState, self._user_id)
