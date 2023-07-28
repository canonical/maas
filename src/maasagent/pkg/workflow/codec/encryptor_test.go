package codec

import (
	"crypto/aes"
	"encoding/hex"
	"testing"

	"github.com/stretchr/testify/assert"
	commonpb "go.temporal.io/api/common/v1"
	"go.temporal.io/sdk/converter"
)

func TestNewEncryptionCodec(t *testing.T) {
	testcases := map[string]struct {
		in  []byte
		err error
	}{
		"empty key": {
			in:  []byte{},
			err: aes.KeySizeError(0),
		},
		"incorrect size key": {
			in:  []byte("incorrect size"),
			err: aes.KeySizeError(14),
		},
		"correct size key": {
			in:  make([]byte, 32),
			err: nil,
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			_, err := NewEncryptionCodec(tc.in)
			assert.Equal(t, tc.err, err)
		})
	}
}

func TestEncodeDecode(t *testing.T) {
	original := "MAAS sensitive data"

	// echo 'MAAS' | sha256sum | head -c 32
	key := []byte("d901193069ad3d2cd99ce75c303f30bc")

	defaultDataConverter := converter.GetDefaultDataConverter()
	originalPayload, err := defaultDataConverter.ToPayload(original)
	assert.NoError(t, err)

	encryptionCodec, err := NewEncryptionCodec(key)
	assert.NoError(t, err)

	encoded, err := encryptionCodec.Encode([]*commonpb.Payload{originalPayload})
	assert.NoError(t, err)

	// Used for testing EncryptionCodec in other languages
	// t.Logf("Temporal encrypted data: %x\f", encoded[0].Data)

	assert.NotEqual(t, originalPayload.Data, encoded[0].Data)

	decoded, err := encryptionCodec.Decode(encoded)
	assert.NoError(t, err)
	assert.Equal(t, originalPayload.Data, decoded[0].Data)
}

func TestDecode(t *testing.T) {
	original := "MAAS sensitive data"
	defaultDataConverter := converter.GetDefaultDataConverter()
	originalPayload, err := defaultDataConverter.ToPayload(original)
	assert.NoError(t, err)

	// Decode payload encoded by EncryptionCodec implemented in Python
	// Check TestEncodeDecode in src/maasserver/workflow/codec/tests/test_encryptor.py
	key := []byte("da720fe6ceb88077ea52c1cd737769c3")

	data, err := hex.DecodeString("de285b79da35289b3cff84c9739a3ec570af661b0a2" +
		"f72cab2955a1de59a5da71a295b8ccf33f6dab0398b3cc6a8b5062c4ca7aaed3e16af5d" +
		"828296777bf13895eeba04fc75e356857538")
	assert.NoError(t, err)

	payload := &commonpb.Payload{
		Metadata: map[string][]byte{
			converter.MetadataEncoding: []byte(MetadataEncodingEncrypted),
		},
		Data: data,
	}

	encryptionCodec, err := NewEncryptionCodec(key)
	assert.NoError(t, err)

	decoded, err := encryptionCodec.Decode([]*commonpb.Payload{payload})
	assert.NoError(t, err)
	assert.Equal(t, originalPayload.Data, decoded[0].Data)
}
