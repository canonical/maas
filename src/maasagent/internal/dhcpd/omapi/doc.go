// Copyright (c) 2023-2024 Canonical Ltd
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

// This package provides a client implementation of the OMAPI protocol
// used for configuring ISC DHCP. It implements a BinaryMarshaler and
// BinaryUnmarshaler for OMAPI messages, HMAC-MD5 authentication and
// a client following the behaviour found in
// github.com/CygnusNetworks/pypureomapi, which is the library
// the previous rackd implementation relied on for OMAPI calls. All
// Messages are sent via TCP.
//
// The OMAPI message structure is as follows:
// Auth ID          [4]byte (uint32) -
// Signature Length [4]byte (uint32) |
// Op Code          [4]byte (uint32) |
// Handle           [4]byte (uint32) Header
// Transaction ID   [4]byte (uint32) |
// Response ID      [4]byte (uint32) -
// Message          [n]byte (map[string][]byte)
// Object           [n]byte (map[string][]byte)
// Signature        [n]byte ([]byte)
//
// Various helper functions are used to work with a OMAPI specific binary format.
// E.g. true/false are represented as 4 bytes.
//
// Message and Object in the Message type contain keys and values.
// Its binary format is as follows:
// Key Length 1   [2]byte (int16)
// Key            [n]byte ([]byte)
// Value Length 1 [4]byte (int32)
// Value          [n]byte ([]byte)
// ...
// Key Length N   [2]byte (int16)
// Key N          [n]byte ([]byte)
// Value Length N [4]byte (int32)
// Value N        [n]byte ([]byte)
// End Key Length [2]byte ([]byte{0x00, 0x00})
//
// Each map provides the length of a key, the key, the length
// of the value and the value in that order. Ordering of the key-value
// does not matter. The end of a map is always noted with
// 0 key length in the form of [0x00, 0x00].
//
// Every OMAPI transaction starts with an Open Op code message,
// its contents varying for the following operations. When a client
// first sends an Open message, it needs to sign the message with an
// authenticator. This package specifically implements a HMAC-MD5 authenticator,
// as this is what has been used historically in MAAS. The Authenticator takes
// the unsigned bytes, computes the hash, and provides it at the end of the message.
//
// Each correct response from the server should be of Op Update. If it is not,
// it should be considered an error response. When a transaction
// requires more than one message, the Handle value should be provided
// in all Messages following the response from the Open Message.
package omapi
