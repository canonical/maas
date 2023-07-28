// Package codec provides Encryption Codec that can be used to encrypt
// sensitive data passed to and from Temporal Server
//
// https://docs.temporal.io/security#data-converter
package codec

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"errors"
	"io"

	commonpb "go.temporal.io/api/common/v1"

	"go.temporal.io/sdk/converter"
)

const (
	MetadataEncodingEncrypted = "binary/encrypted"
)

// EncryptionCodec implements PayloadCodec using AES Crypt.
type EncryptionCodec struct {
	cipher cipher.AEAD
}

func NewEncryptionCodec(key []byte) (*EncryptionCodec, error) {
	c, err := aes.NewCipher(key)
	if err != nil {
		return nil, err
	}

	gcm, err := cipher.NewGCM(c)
	if err != nil {
		return nil, err
	}

	return &EncryptionCodec{cipher: gcm}, err
}

// Encode implements converter.PayloadCodec.Encode.
func (c *EncryptionCodec) Encode(payloads []*commonpb.Payload) ([]*commonpb.Payload, error) {
	result := make([]*commonpb.Payload, len(payloads))

	for i, p := range payloads {
		origBytes, err := p.Marshal()
		if err != nil {
			return payloads, err
		}

		nonce := make([]byte, c.cipher.NonceSize())
		if _, err = io.ReadFull(rand.Reader, nonce); err != nil {
			return nil, err
		}

		b, err := c.cipher.Seal(nonce, nonce, origBytes, nil), nil

		result[i] = &commonpb.Payload{
			Metadata: map[string][]byte{
				converter.MetadataEncoding: []byte(MetadataEncodingEncrypted),
			},
			Data: b,
		}
	}

	return result, nil
}

// Decode implements converter.PayloadCodec.Decode.
func (c *EncryptionCodec) Decode(payloads []*commonpb.Payload) ([]*commonpb.Payload, error) {
	result := make([]*commonpb.Payload, len(payloads))

	for i, p := range payloads {
		// Only if it's encrypted
		if string(p.Metadata[converter.MetadataEncoding]) != MetadataEncodingEncrypted {
			result[i] = p
			continue
		}

		nonceSize := c.cipher.NonceSize()
		if len(p.Data) < nonceSize {
			return nil, errors.New("data length is less than nonce size")
		}

		nonce, data := p.Data[:nonceSize], p.Data[nonceSize:]

		b, err := c.cipher.Open(nil, nonce, data, nil)
		if err != nil {
			return payloads, err
		}

		result[i] = &commonpb.Payload{}

		err = result[i].Unmarshal(b)
		if err != nil {
			return payloads, err
		}
	}

	return result, nil
}
