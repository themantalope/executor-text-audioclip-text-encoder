from pathlib import Path
from typing import List

import pytest
from executor.audioclip_text import AudioCLIPTextEncoder
from jina import Document, DocumentArray, Executor

_EMBEDDING_DIM = 1024


@pytest.fixture(scope='module')
def basic_encoder() -> AudioCLIPTextEncoder:
    return AudioCLIPTextEncoder(
        model_path=str(Path(__file__).parents[2] / '.cache/AudioCLIP-Full-Training.pt'),
        tokenizer_path=str(
            Path(__file__).parents[2] / '.cache/bpe_simple_vocab_16e6.txt.gz'
        ),
    )


def test_config():
    ex = Executor.load_config(
        str(Path(__file__).parents[2] / 'config.yml'),
        override_with={
            'model_path': str(
                Path(__file__).parents[2] / '.cache/AudioCLIP-Full-Training.pt'
            ),
            'tokenizer_path': str(
                Path(__file__).parents[2] / '.cache/bpe_simple_vocab_16e6.txt.gz'
            ),
        },
    )
    assert ex.batch_size == 32


def test_no_document(basic_encoder: AudioCLIPTextEncoder):
    basic_encoder.encode(None, {})


def test_empty_documents(basic_encoder: AudioCLIPTextEncoder):
    docs = DocumentArray([])
    basic_encoder.encode(docs, {})
    assert len(docs) == 0


def test_no_text_documents(basic_encoder: AudioCLIPTextEncoder):
    docs = DocumentArray([Document()])
    basic_encoder.encode(docs, {})
    assert len(docs) == 1
    assert docs[0].embedding is None


def test_encoding_cpu():
    enc = AudioCLIPTextEncoder(device='cpu')
    input_data = DocumentArray([Document(text='hello world')])

    enc.encode(docs=input_data, parameters={})

    assert input_data[0].embedding.shape == (_EMBEDDING_DIM,)


@pytest.mark.gpu
def test_encoding_gpu():
    enc = AudioCLIPTextEncoder(device='cuda', download_model=True)
    input_data = DocumentArray([Document(text='hello world')])

    enc.encode(docs=input_data, parameters={})

    assert input_data[0].embedding.shape == (_EMBEDDING_DIM,)


@pytest.mark.parametrize(
    'traversal_paths, counts',
    [
        ('@r', [['@r', 1], ['@c', 0], ['@cc', 0]]),
        ('@c', [['@r', 0], ['@c', 3], ['@cc', 0]]),
        ('@cc', [['@r', 0], ['@c', 0], ['@cc', 2]]),
        ('@cc,r', [['@r', 1], ['@c', 0], ['@cc', 2]]),
    ],
)
def test_traversal_path(
    traversal_paths: str, counts: List, basic_encoder: AudioCLIPTextEncoder
):
    text = 'blah'
    docs = DocumentArray([Document(id='root1', text=text)])
    docs[0].chunks = [
        Document(id='chunk11', text=text),
        Document(id='chunk12', text=text),
        Document(id='chunk13', text=text),
    ]
    docs[0].chunks[0].chunks = [
        Document(id='chunk111', text=text),
        Document(id='chunk112', text=text),
    ]

    basic_encoder.encode(docs=docs, parameters={'traversal_paths': traversal_paths})
    for path, count in counts:
        embeddings = docs[path].embeddings
        if count != 0 :
            assert len([em for em in embeddings if em is not None]) == count
        else:
            assert embeddings is None


@pytest.mark.parametrize('batch_size', [1, 2, 4, 8])
def test_batch_size(basic_encoder: AudioCLIPTextEncoder, batch_size: int):
    docs = DocumentArray([Document(text='hello there') for _ in range(32)])
    basic_encoder.encode(docs, parameters={'batch_size': batch_size})

    for doc in docs:
        assert doc.embedding.shape == (_EMBEDDING_DIM,)


def test_quality_embeddings(basic_encoder: AudioCLIPTextEncoder):
    docs = DocumentArray(
        [
            Document(id='A', text='a furry animal that with a long tail'),
            Document(id='B', text='a domesticated mammal with four legs'),
            Document(id='C', text='a type of aircraft that uses rotating wings'),
            Document(id='D', text='flying vehicle that has fixed wings and engines'),
        ]
    )

    basic_encoder.encode(DocumentArray(docs), {})

    # assert semantic meaning is captured in the encoding
    docs.match(docs)
    matches = ['B', 'A', 'D', 'C']
    for i, doc in enumerate(docs):
        assert doc.matches[1].id == matches[i]
