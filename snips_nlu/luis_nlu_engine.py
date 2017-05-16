import time
from luis_bench.lib.intent_tools import add_examples, train_model, publish_app
from luis_bench.lib.intent_tools import delete_all, create_intent, \
    create_entity
from luis_bench.lib.parser_tools import parser

from dataset import validate_and_format_dataset
from snips_nlu.nlu_engine import NLUEngine
from snips_nlu.result import IntentClassificationResult
from snips_nlu.result import ParsedSlot
from snips_nlu.result import Result
from snips_nlu.utils import get_intents_and_entities


class ApiaiNLUEngine(NLUEngine):
    def __init__(self, language,
                 token="1ed49ac5bb5742f7a3b9d783ae5948c9",
                 appId="1117a29b-5f7a-45ba-98c8-5cb665427a55",
                 versionId="1.0"):

        super(ApiaiNLUEngine, self).__init__(language)

        self.token = token
        self.appId = appId
        self.versionId = versionId

    def parse(self, text):
        """
        Parse the input text and returns a dictionary containing the most
        likely intent and slots.
        """
        parser(text, self.appId, self.token)

        if len(res['intent']) == 0:
            intent_name = None
            prob = None
            slots = []
        else:
            intent_name = res['intent']['slug']
            prob = res['intent']['confidence']
            slots = res['entities']

        intent_res = IntentClassificationResult(intent_name, prob)

        valid_slot = []
        for slot in slots:
            slot_value = slot['value']
            slot_name = slot['name']
            match_range = [slot['range'][0], slot['range'][1]]

            s = ParsedSlot(match_range, slot_value, 'whathever', slot_name)

            valid_slot.append(s)

        return Result(text, parsed_intent=intent_res,
                      parsed_slots=valid_slot).as_dict()

    def fit(self, dataset):
        """
        Fit the engine with a dataset and return it
        :param dataset: A dictionary containing data of the custom and builtin 
        intents.
        See https://github.com/snipsco/snips-nlu/blob/develop/README.md for
        details about the format.
        :return: A fitted ApiaiNLUEngine
        """
        dataset = validate_and_format_dataset(dataset)

        self.intents, self.entities = get_intents_and_entities(dataset)

        # reinitialize agent
        delete_all(appId, versionId, token)

        # create intent and entities
        for intent in self.intents:
            create_intent(intent, appId, versionId, token)

        mapping_builtin = {
            'timeRange': 'datetimeV2'
        }

        for entity in self.entities:
            if entity not in mapping_builtin:
                create_entity(entity, appId, versionId, token)
            else:
                entity_builtin = mapping_builtin[entity]
                create_entity_builtin(entity_builtin, appId, versionId, token)

        # dumping labelled queries
        userSays = []
        for intent in self.intents:
            for query in dataset['intents'][intent]['utterances']:
                source = ''.join([chunk['text'] for chunk in query['data']])

                to_add = {
                    'text': source,
                    'intentName': intent,
                    'entityLabels': []
                }
                for chunk in query['data']:
                    if 'entity' in chunk:
                        spans = re.search(chunk['text'], source).span()
                        if chunk['entity'] in mapping_builtin:
                            to_add['entityLabels'].append(
                                {
                                    'startCharIndex': spans[0],
                                    'endCharIndex': spans[1],
                                    'entityName': mapping_builtin[
                                        chunk['entity']]
                                }
                            )
                        else:
                            to_add['entityLabels'].append(
                                {
                                    'startCharIndex': spans[0],
                                    'endCharIndex': spans[1],
                                    'entityName': chunk['entity'],
                                }
                            )

                userSays.append(to_add)

        add_examples(userSays, self.appId, self.versionId, self.token)

        # train model
        train_model(self.appId, self.versionId, self.token)
        publish_app(self.appId, self.versionId, self.token)

        return self