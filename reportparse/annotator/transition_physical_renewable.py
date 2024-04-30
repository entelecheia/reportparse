from logging import getLogger
import argparse

from transformers import AutoTokenizer, AutoModelForSequenceClassification

from reportparse.annotator.base import BaseAnnotator
from reportparse.structure.document import Document
from reportparse.util.plm_classifier import annotate_by_sequence_classification


@BaseAnnotator.register("transition_physical_renewable")
class TransitionPhysicalRenewableAnnotator(BaseAnnotator):

    """
    This class is an annotator of https://huggingface.co/climatebert/transition-physical
    According to the README of the model,
    > This is the fine-tuned ClimateBERT language model with a classification head for detecting sentences
    > that are either related to transition risks or to physical climate risks.
    > Using the climatebert/distilroberta-base-climate-f language model as starting point,
    > the distilroberta-base-climate-detector model is fine-tuned on our human-annotated dataset.

    @article{deng2023war,
        title={War and Policy: Investor Expectations on the Net-Zero Transition},
        author={Deng, Ming and Leippold, Markus and Wagner, Alexander F and Wang, Qian},
        journal={Swiss Finance Institute Research Paper},
        number={22-29},
        year={2023}
    }
    """

    def __init__(self):
        super().__init__()
        self.transition_physical_tokenizer = None
        self.transition_physical_model = None
        self.transition_physical_model_name_or_path = 'climatebert/transition-physical'
        self.transition_physical_tokenizer_name_or_path = 'climatebert/distilroberta-base-climate-detector'
        self.transition_physical_label_map = {
            'LABEL_0': 'transition_risk', 'LABEL_1': 'none', 'LABEL_2': 'physical_risk',
        }
        self.renewable_tokenizer = None
        self.renewable_model = None
        self.renewable_model_name_or_path = 'climatebert/renewable'
        self.renewable_tokenizer_name_or_path = 'climatebert/distilroberta-base-climate-detector'
        return

    def annotate(
        self,
        document: Document, args=None,
        max_len=128, batch_size=8, level='block', target_layouts=('text', 'list')
    ) -> Document:
        logger = getLogger(__name__)

        if args is None:
            logger.warning('The "annotate" method received the "args" argument, '
                           'which means any other optional arguments will be ignored.')

        max_len = args.transition_physical_renewable_max_len if args is not None else max_len
        batch_size = args.transition_physical_renewable_batch_size if args is not None else batch_size
        level = args.transition_physical_renewable_level if args is not None else level
        target_layouts = args.transition_physical_renewable_target_layouts if args is not None else target_layouts

        assert level in ['block', 'sentence']
        assert max_len > 0
        assert batch_size > 0
        assert set(target_layouts) & {'title', 'text', 'list'}

        if self.transition_physical_tokenizer is None or self.transition_physical_model is None:
            self.transition_physical_tokenizer = AutoTokenizer.from_pretrained(
                self.transition_physical_tokenizer_name_or_path,
                max_len=max_len
            )
            self.transition_physical_model = AutoModelForSequenceClassification.from_pretrained(
                self.transition_physical_model_name_or_path
            )
        if self.renewable_tokenizer is None or self.renewable_model is None:
            self.renewable_tokenizer = AutoTokenizer.from_pretrained(
                self.renewable_tokenizer_name_or_path,
                max_len=max_len
            )
            self.renewable_model = AutoModelForSequenceClassification.from_pretrained(
                self.renewable_model_name_or_path
            )

        # Get renewable related mentions
        document_renewable_annot = annotate_by_sequence_classification(
            annotator_name='dummy',
            document=document,
            tokenizer=self.renewable_tokenizer,
            model=self.renewable_model,
            level=level,
            target_layouts=target_layouts,
            batch_size=batch_size
        )
        renewable_object_id2score = dict()
        for annot_obj, annot in document_renewable_annot.find_annotations_by_annotator_name('dummy'):
            if annot.value == 'LABEL_1':
                renewable_object_id2score[annot_obj.id] = annot.meta['score']

        document = annotate_by_sequence_classification(
            annotator_name='transition_physical_renewable',
            document=document,
            tokenizer=self.transition_physical_tokenizer,
            model=self.transition_physical_model,
            level=level,
            target_layouts=target_layouts,
            batch_size=batch_size
        )
        for annot_obj, annot in document.find_annotations_by_annotator_name('transition_physical_renewable'):
            new_label = self.transition_physical_label_map[annot.value]
            if new_label == 'transition_risk' and annot_obj.id in renewable_object_id2score.keys():
                new_label += '-renewable_energy'
                annot.meta['score'] = renewable_object_id2score[annot_obj.id]
            annot.set_value(new_label)

        return document

    def add_argument(self, parser: argparse.ArgumentParser):
        parser.add_argument(
            '--transition_physical_renewable_max_len',
            type=int,
            default=128
        )
        parser.add_argument(
            '--transition_physical_renewable_batch_size',
            type=int,
            default=8
        )
        parser.add_argument(
            '--transition_physical_renewable_level',
            type=str,
            choices=['sentence', 'block'],
            default='block'
        )
        parser.add_argument(
            '--transition_physical_renewable_target_layouts',
            type=str,
            nargs='+',
            default=['text', 'list']
        )

