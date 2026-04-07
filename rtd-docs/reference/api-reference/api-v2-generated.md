# MAAS API v2 Reference

This is the documentation for the API that lets you control and query MAAS. You can find out more about MAAS at [https://maas.io/](https://maas.io/).

## API Information

**Version:** 2.0.0

**License:** [GNU Affero General Public License version 3](https://www.gnu.org/licenses/agpl-3.0.en.html)

## Bcache Cache Set

Operations for bcache cache set resources.

````{dropdown} DELETE /MAAS/api/2.0/nodes/{system_id}/bcache-cache-set/{id}/: Delete a bcache set

  Delete bcache cache set on a machine.

  **Operation ID:** `BcacheCacheSetHandler_delete`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A machine system_id.
  - **`{id}`** (*string*, path parameter, Required): A cache_set_id.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 400 BAD REQUEST**
  
  The cache set is in use.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/bcache-cache-set/{id}/: Read a bcache cache set

  Read bcache cache set on a machine.

  **Operation ID:** `BcacheCacheSetHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A machine system_id.
  - **`{id}`** (*string*, path parameter, Required): A cache_set_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a bcache set.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/nodes/{system_id}/bcache-cache-set/{id}/: Update a bcache set

  Update bcache cache set on a machine.
Note: specifying both a cache_device and a cache_partition is not allowed.

  **Operation ID:** `BcacheCacheSetHandler_update`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A machine system_id.
  - **`{id}`** (*string*, path parameter, Required): A cache_set_id.

  **Request body (multipart/form-data):**

  - **`cache_device`** (*string*, Optional): Cache block device to replace current one.
  - **`cache_partition`** (*string*, Optional): Cache partition to replace current one.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a bcache set.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

## Bcache Cache Sets

Operations for bcache cache sets resources.

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/bcache-cache-sets/: List bcache sets

  List all bcache cache sets belonging to a machine.

  **Operation ID:** `BcacheCacheSetsHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A machine system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of bcache sets.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/bcache-cache-sets/: Creates a bcache cache set

  Creates a bcache cache set.
Note: specifying both a cache_device and a cache_partition is not allowed.

  **Operation ID:** `BcacheCacheSetsHandler_create`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A machine system_id.

  **Request body (multipart/form-data):**

  - **`cache_device`** (*string*, Optional): Cache block device.
  - **`cache_partition`** (*string*, Optional): Cache partition.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new bcache set.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

## Bcache Device

Operations for bcache device resources.

````{dropdown} DELETE /MAAS/api/2.0/nodes/{system_id}/bcache/{id}/: Delete a bcache

  Delete bcache on a machine.

  **Operation ID:** `BcacheHandler_delete`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine's system_id.
  - **`{id}`** (*string*, path parameter, Required): The bcache id.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested id or system_id is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/bcache/{id}/: Read a bcache device

  Read bcache device on a machine.

  **Operation ID:** `BcacheHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine's system_id.
  - **`{id}`** (*string*, path parameter, Required): The bcache id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the bcache device.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine or bcache id is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/nodes/{system_id}/bcache/{id}/: Update a bcache

  Update bcache on a machine.
Specifying both a device and a partition for a given role (cache or backing) is not allowed.

  **Operation ID:** `BcacheHandler_update`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine's system_id.
  - **`{id}`** (*string*, path parameter, Required): The bcache id.

  **Request body (multipart/form-data):**

  - **`backing_device`** (*string*, Optional): Backing block device to replace current one.
  - **`backing_partition`** (*string*, Optional): Backing partition to replace current one.
  - **`cache_mode`** (*string*, Optional): Cache mode: `WRITEBACK`, `WRITETHROUGH`, `WRITEAROUND`.
  - **`cache_set`** (*string*, Optional): Cache set to replace current one.
  - **`name`** (*string*, Optional): Name of the Bcache.
  - **`uuid`** (*string*, Optional): UUID of the Bcache.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new bcache device.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested id or system_id is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

## Bcache Devices

Operations for bcache devices resources.

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/bcaches/: List all bcache devices

  List all bcache devices belonging to a machine.

  **Operation ID:** `BcachesHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine's system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of bcache devices.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested system_id is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/bcaches/: Creates a bcache

  Creates a bcache.
Specifying both a device and a partition for a given role (cache or backing) is not allowed.

  **Operation ID:** `BcachesHandler_create`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine's system_id.

  **Request body (multipart/form-data):**

  - **`backing_device`** (*string*, Optional): Backing block device.
  - **`backing_partition`** (*string*, Optional): Backing partition.
  - **`cache_mode`** (*string*, Optional): Cache mode: `WRITEBACK`, `WRITETHROUGH`, `WRITEAROUND`.
  - **`cache_set`** (*string*, Optional): Cache set.
  - **`name`** (*string*, Optional): Name of the Bcache.
  - **`uuid`** (*string*, Optional): UUID of the Bcache.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new bcache device.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested system_id is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

## Block device

Operations for block device resources.

````{dropdown} DELETE /MAAS/api/2.0/nodes/{system_id}/blockdevices/{id}/: Delete a block device

  Delete block device on a given machine.

  **Operation ID:** `BlockDeviceHandler_delete`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id.
  - **`{id}`** (*string*, path parameter, Required): The block device's id.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The user does not have permissions to delete the block device.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine or block device is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/blockdevices/{id}/: Read a block device

  Read a block device on a given machine.

  **Operation ID:** `BlockDeviceHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id.
  - **`{id}`** (*string*, path parameter, Required): The block device's id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested block device.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine or block device is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/nodes/{system_id}/blockdevices/{id}/: Update a block device

  Update block device on a given machine.
Machines must have a status of Ready to have access to all options.
Machines with Deployed status can only have the name, model, serial, and/or id_path updated for a block device. This is intented to allow a bad block device to be replaced while the machine remains deployed.

  **Operation ID:** `BlockDeviceHandler_update`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id.
  - **`{id}`** (*string*, path parameter, Required): The block device's id.

  **Request body (multipart/form-data):**

  - **`block_size`** (*string*, Optional): (Physical devices) Block size of the block device.
  - **`id_path`** (*string*, Optional): (Physical devices) Only used if model and serial cannot be provided. This should be a path that is fixed and doesn't change depending on the boot order or kernel version.
  - **`model`** (*string*, Optional): (Physical devices) Model of the block device.
  - **`name`** (*string*, Optional): (Virtual devices) Name of the block device.
  - **`serial`** (*string*, Optional): (Physical devices) Serial number of the block device.
  - **`size`** (*string*, Optional): (Virtual devices) Size of the block device. (Only allowed for logical volumes.)
  - **`uuid`** (*string*, Optional): (Virtual devices) UUID of the block device.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated block device.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permissions to update the block device.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine or block device is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/blockdevices/{id}/op-add_tag: Add a tag

  Add a tag to block device on a given machine.

  **Operation ID:** `BlockDeviceHandler_add_tag`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id.
  - **`{id}`** (*string*, path parameter, Required): The block device's id.

  **Request body (multipart/form-data):**

  - **`tag`** (*string*, Required): The tag being added.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated block device.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permissions to add a tag.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine or block device is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/blockdevices/{id}/op-format: Format block device

  Format block device with filesystem.

  **Operation ID:** `BlockDeviceHandler_format`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id.
  - **`{id}`** (*string*, path parameter, Required): The block device's id.

  **Request body (multipart/form-data):**

  - **`fstype`** (*string*, Required): Type of filesystem.
  - **`uuid`** (*string*, Optional): UUID of the filesystem.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated block device.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permissions to format the block device.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine or block device is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/blockdevices/{id}/op-mount: Mount a filesystem

  Mount the filesystem on block device.

  **Operation ID:** `BlockDeviceHandler_mount`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id.
  - **`{id}`** (*string*, path parameter, Required): The block device's id.

  **Request body (multipart/form-data):**

  - **`mount_options`** (*string*, Optional): Options to pass to mount(8).
  - **`mount_point`** (*string*, Required): Path on the filesystem to mount.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated block device.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permissions to mount the filesystem.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine or block device is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/blockdevices/{id}/op-remove_tag: Remove a tag

  Remove a tag from block device on a given machine.

  **Operation ID:** `BlockDeviceHandler_remove_tag`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id.
  - **`{id}`** (*string*, path parameter, Required): The block device's id.

  **Request body (multipart/form-data):**

  - **`tag`** (*string*, Optional): The tag being removed.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated block device.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permissions to remove a tag.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine or block device is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/blockdevices/{id}/op-set_boot_disk: Set boot disk

  Set a block device as the boot disk for the machine.

  **Operation ID:** `BlockDeviceHandler_set_boot_disk`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id.
  - **`{id}`** (*string*, path parameter, Required): The block device's id.

  **Responses:**

  **HTTP 200 OK**
  
  Boot disk set.
  
  Content type: `text/plain`

  **HTTP 400 BAD REQUEST**
  
  The block device is a virtual block device.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permissions to set the boot disk.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine or block device is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/blockdevices/{id}/op-unformat: Unformat a block device

  Unformat a previously formatted block device.

  **Operation ID:** `BlockDeviceHandler_unformat`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id.
  - **`{id}`** (*string*, path parameter, Required): The block device's id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated block device.
  
  Content type: `application/json`

  **HTTP 400 BAD REQUEST**
  
  The block device is not formatted, currently mounted, or part of a filesystem group.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permissions to unformat the block device.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine or block device is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/blockdevices/{id}/op-unmount: Unmount a filesystem

  Unmount the filesystem on block device.

  **Operation ID:** `BlockDeviceHandler_unmount`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id.
  - **`{id}`** (*string*, path parameter, Required): The block device's id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated block device.
  
  Content type: `application/json`

  **HTTP 400 BAD REQUEST**
  
  The block device is not formatted or currently mounted.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permissions to mount the filesystem.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine or block device is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

## Block devices

Operations for block devices resources.

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/blockdevices/: List block devices

  List all block devices belonging to a machine.

  **Operation ID:** `BlockDevicesHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of block devices.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/blockdevices/: Create a block device

  Create a physical block device.

  **Operation ID:** `BlockDevicesHandler_create`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id.

  **Request body (multipart/form-data):**

  - **`block_size`** (*string*, Required): Block size of the block device.
  - **`id_path`** (*string*, Optional): Only used if model and serial cannot be provided. This should be a path that is fixed and doesn't change depending on the boot order or kernel version.
  - **`model`** (*string*, Optional): Model of the block device.
  - **`name`** (*string*, Required): Name of the block device.
  - **`serial`** (*string*, Optional): Serial number of the block device.
  - **`size`** (*string*, Required): Size of the block device.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new block device.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

## Boot resource

Operations for boot resource resources.

````{dropdown} DELETE /MAAS/api/2.0/boot-resources/{id}/: Delete a boot resource

  Delete a boot resource by id.

  **Operation ID:** `BootResourceHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The boot resource id.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested boot resource is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/boot-resources/{id}/: Read a boot resource

  Reads a boot resource by id

  **Operation ID:** `BootResourceHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The boot resource id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the requested resource.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested boot resource is not found.
  
  Content type: `text/plain`

````

## Boot resource file upload

Operations for boot resource file upload resources.

````{dropdown} PUT /MAAS/api/2.0/boot-resources/{resource_id}/upload/{id}/: Upload chunk of boot resource file.

  Uploads a chunk of boot resource file

  **Operation ID:** `BootResourceFileUploadHandler_update`

  **Parameters:**

  - **`{resource_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{resource_id}`** (*integer*, path parameter, Required): The boot resource id.
  - **`{id}`** (*integer*, path parameter, Required): The boot resource file id.

  **Responses:**

  **HTTP 200 OK**
  
  200

  **HTTP 400 BAD REQUEST**
  
  Error while uploading the file.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user tried to upload to a boot resource of wrong type.
  
  Content type: `text/plain`

````

## Boot resources

Operations for boot resources resources.

````{dropdown} GET /MAAS/api/2.0/boot-resources/: List boot resources

  List all boot resources

  **Operation ID:** `BootResourcesHandler_read`

  **Parameters:**

  - **`type`** (*string*, Optional): Type of boot resources to list. If not provided, returns all types.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of boot resource objects.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/boot-resources/: Create a new boot resource

  Creates a new boot resource. The file upload must be done in chunk, see Boot resource file upload.

  **Operation ID:** `BootResourcesHandler_create`

  **Request body (multipart/form-data):**

  - **`architecture`** (*string*, Required): Architecture the boot resource supports.
  - **`base_image`** (*string*, Optional): The Base OS image a custom image is built on top of. Only required for custom image.
  - **`filetype`** (*string*, Optional): Filetype for uploaded content. (Default: `tgz`. Supported: `tgz`, `tbz`, `txz`, `ddtgz`, `ddtbz`, `ddtxz`, `ddtar`, `ddbz2`, `ddgz`, `ddxz`, `ddraw`)
  - **`name`** (*string*, Required): Name of the boot resource.
  - **`sha256`** (*string*, Required): The `sha256` hash of the resource.
  - **`size`** (*string*, Required): The size of the resource in bytes.
  - **`title`** (*string*, Optional): Title for the boot resource.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the uploaded resource.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/boot-resources/op-import: Import boot resources

  Import the boot resources.

  **Operation ID:** `BootResourcesHandler_import`

  **Responses:**

  **HTTP 200 OK**
  
  Import of boot resources started
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/boot-resources/op-is_importing: Importing status

  Get the status of importing resources.

  **Operation ID:** `BootResourcesHandler_is_importing`

  **Responses:**

  **HTTP 200 OK**
  
  true
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/boot-resources/op-stop_import: Stop import boot resources

  Stop import the boot resources.

  **Operation ID:** `BootResourcesHandler_stop_import`

  **Responses:**

  **HTTP 200 OK**
  
  Import of boot resources is being stopped.
  
  Content type: `text/plain`

````

## Boot source

Operations for boot source resources.

````{dropdown} DELETE /MAAS/api/2.0/boot-sources/{id}/: Delete a boot source

  Delete a boot source with the given id.

  **Operation ID:** `BootSourceHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): A boot-source id.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested boot-source is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/boot-sources/{id}/: Read a boot source

  Read a boot source with the given id.

  **Operation ID:** `BootSourceHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): A boot-source id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested boot-source object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested boot-source is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/boot-sources/{id}/: Update a boot source

  Update a boot source with the given id.

  **Operation ID:** `BootSourceHandler_update`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): A boot-source id.

  **Request body (multipart/form-data):**

  - **`keyring_data`** (*string*, Optional): The GPG keyring for this BootSource, base64-encoded data.
  - **`keyring_filename`** (*string*, Optional): The path to the keyring file for this BootSource.
  - **`url`** (*string*, Optional): The URL of the BootSource.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated boot-source object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested boot-source is not found.
  
  Content type: `text/plain`

````

## Boot source selection

Operations for boot source selection resources.

````{dropdown} DELETE /MAAS/api/2.0/boot-sources/{boot_source_id}/selections/{id}/: Delete a boot source

  Delete a boot source with the given id.

  **Operation ID:** `BootSourceSelectionHandler_delete`

  **Parameters:**

  - **`{boot_source_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{boot_source_id}`** (*string*, path parameter, Required): A boot-source id.
  - **`{id}`** (*string*, path parameter, Required): A boot-source selection id.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested boot-source or boot-source selection is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/boot-sources/{boot_source_id}/selections/{id}/: Read a boot source selection

  Read a boot source selection with the given id.

  **Operation ID:** `BootSourceSelectionHandler_read`

  **Parameters:**

  - **`{boot_source_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{boot_source_id}`** (*string*, path parameter, Required): A boot-source id.
  - **`{id}`** (*string*, path parameter, Required): A boot-source selection id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested boot-source selection object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested boot-source or boot-source selection is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/boot-sources/{boot_source_id}/selections/{id}/: Update a boot-source selection

  Update a boot source selection with the given id.

  **Operation ID:** `BootSourceSelectionHandler_update`

  **Parameters:**

  - **`{boot_source_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{boot_source_id}`** (*string*, path parameter, Required): A boot-source id.
  - **`{id}`** (*string*, path parameter, Required): A boot-source selection id.

  **Request body (multipart/form-data):**

  - **`arches`** (*string*, Optional): The list of architectures for which to import resources.
  - **`labels`** (*string*, Optional): The list of labels for which to import resources.
  - **`os`** (*string*, Optional): The OS (e.g. ubuntu, centos) for which to import resources.
  - **`release`** (*string*, Optional): The release for which to import resources.
  - **`subarches`** (*string*, Optional): The list of sub-architectures for which to import resources.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested boot-source selection object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested boot-source or boot-source selection is not found.
  
  Content type: `text/plain`

````

## Boot source selections

Operations for boot source selections resources.

````{dropdown} GET /MAAS/api/2.0/boot-sources/{boot_source_id}/selections/: List boot-source selections

  List all available boot-source selections.

  **Operation ID:** `BootSourceSelectionsHandler_read`

  **Parameters:**

  - **`{boot_source_id}`** (*string*, path parameter, Required): 
  - **`{boot_source_id}`** (*string*, path parameter, Required): A boot-source id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of all available boot-source selections.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested boot-source is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/boot-sources/{boot_source_id}/selections/: Create a boot-source selection

  Create a new boot source selection.

  **Operation ID:** `BootSourceSelectionsHandler_create`

  **Parameters:**

  - **`{boot_source_id}`** (*string*, path parameter, Required): 
  - **`{boot_source_id}`** (*string*, path parameter, Required): A boot-source id.

  **Request body (multipart/form-data):**

  - **`arches`** (*string*, Optional): The architecture list for which to import resources.
  - **`labels`** (*string*, Optional): The label lists for which to import resources.
  - **`os`** (*string*, Optional): The OS (e.g. ubuntu, centos) for which to import resources.
  - **`release`** (*string*, Optional): The release for which to import resources.
  - **`subarches`** (*string*, Optional): The subarchitecture list for which to import resources.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new boot-source selection.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested boot-source is not found.
  
  Content type: `text/plain`

````

## Boot sources

Operations for boot sources resources.

````{dropdown} GET /MAAS/api/2.0/boot-sources/: List boot sources

  List all boot sources.

  **Operation ID:** `BootSourcesHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of all available boot-source objects.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/boot-sources/: Create a boot source

  Create a new boot source. Note that in addition to `url`, you must supply either `keyring_data` or `keyring_filename`.

  **Operation ID:** `BootSourcesHandler_create`

  **Request body (multipart/form-data):**

  - **`keyring_data`** (*string*, Optional): The GPG keyring for this BootSource, base64-encoded.
  - **`keyring_filename`** (*string*, Optional): The path to the keyring file for this BootSource.
  - **`url`** (*string*, Required): The URL of the BootSource.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new boot source.
  
  Content type: `application/json`

````

## Commissioning results

Operations for commissioning results resources.

````{dropdown} GET /MAAS/api/2.0/installation-results/: Read commissioning results

  Read the commissioning results per node visible to the user, optionally filtered.

  **Operation ID:** `NodeResultsHandler_read`

  **Parameters:**

  - **`system_id`** (*string*, Optional): An optional list of system ids. Only the results related to the nodes with these system ids will be returned.
  - **`name`** (*string*, Optional): An optional list of names. Only the results with the specified names will be returned.
  - **`result_type`** (*string*, Optional): An optional result_type. Only the results with the specified result_type will be returned.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of the requested installation-result objects.
  
  Content type: `application/json`

````

## Commissioning script (deprecated)

Operations for commissioning script (deprecated) resources.

````{dropdown} ~~DELETE /MAAS/api/2.0/commissioning-scripts/{name}: CommissioningScriptHandler delete~~

  Manage a custom commissioning script.
This functionality is only available to administrators.
The 'Commissioning-script' endpoint has been deprecated in favour of 'Node-Script'.

  ```{warning}
  This endpoint is deprecated.
  ```

  **Operation ID:** `CommissioningScriptHandler_delete`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested script is not found.
  
  Content type: `text/plain`

````

````{dropdown} ~~GET /MAAS/api/2.0/commissioning-scripts/{name}: CommissioningScriptHandler read~~

  Manage a custom commissioning script.
This functionality is only available to administrators.
The 'Commissioning-script' endpoint has been deprecated in favour of 'Node-Script'.

  ```{warning}
  This endpoint is deprecated.
  ```

  **Operation ID:** `CommissioningScriptHandler_read`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the script.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested script is not found.
  
  Content type: `text/plain`

````

````{dropdown} ~~PUT /MAAS/api/2.0/commissioning-scripts/{name}: CommissioningScriptHandler update~~

  Manage a custom commissioning script.
This functionality is only available to administrators.
The 'Commissioning-script' endpoint has been deprecated in favour of 'Node-Script'.

  ```{warning}
  This endpoint is deprecated.
  ```

  **Operation ID:** `CommissioningScriptHandler_update`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the updated script.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested script is not found.
  
  Content type: `text/plain`

````

## Commissioning scripts (deprecated)

Operations for commissioning scripts (deprecated) resources.

````{dropdown} ~~GET /MAAS/api/2.0/commissioning-scripts/: CommissioningScriptsHandler read~~

  Manage custom commissioning scripts.
This functionality is only available to administrators.
The 'Commissioning-scripts' endpoint has been deprecated in favour of 'Node-Scripts'.

  ```{warning}
  This endpoint is deprecated.
  ```

  **Operation ID:** `CommissioningScriptsHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of script objects.
  
  Content type: `application/json`

````

````{dropdown} ~~POST /MAAS/api/2.0/commissioning-scripts/: CommissioningScriptsHandler create~~

  Manage custom commissioning scripts.
This functionality is only available to administrators.
The 'Commissioning-scripts' endpoint has been deprecated in favour of 'Node-Scripts'.

  ```{warning}
  This endpoint is deprecated.
  ```

  **Operation ID:** `CommissioningScriptsHandler_create`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the new script.
  
  Content type: `application/json`

````

## DHCP Snippet (deprecated)

Operations for dhcp snippet (deprecated) resources.

````{dropdown} ~~DELETE /MAAS/api/2.0/dhcp-snippets/{id}/: Delete a DHCP snippet~~

  Delete a DHCP snippet with the given id.

  ```{warning}
  This endpoint is deprecated.
  ```

  **Operation ID:** `DHCPSnippetHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A DHCP snippet id.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to delete the reserved IP.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested reserved IP is not found.
  
  Content type: `text/plain`

````

````{dropdown} ~~GET /MAAS/api/2.0/dhcp-snippets/{id}/: Read a DHCP snippet~~

  Read a DHCP snippet with the given id.

  ```{warning}
  This endpoint is deprecated.
  ```

  **Operation ID:** `DHCPSnippetHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A DHCP snippet id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of reserved IPs.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested reserved IP is not found.
  
  Content type: `text/plain`

````

````{dropdown} ~~PUT /MAAS/api/2.0/dhcp-snippets/{id}/: Update a DHCP snippet~~

  Update a DHCP snippet with the given id.

  ```{warning}
  This endpoint is deprecated.
  ```

  **Operation ID:** `DHCPSnippetHandler_update`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A DHCP snippet id.

  **Request body (multipart/form-data):**

  - **`description`** (*string*, Optional): A description of what the DHCP snippet does.
  - **`enabled`** (*boolean*, Optional): Whether or not the DHCP snippet is currently enabled.
  - **`global_snippet`** (*boolean*, Optional): Set the DHCP snippet to be a global option. This removes any node or subnet links.
  - **`name`** (*string*, Optional): The name of the DHCP snippet.
  - **`node`** (*string*, Optional): The node the DHCP snippet is to be used for. Can not be set if subnet is set.
  - **`subnet`** (*string*, Optional): The subnet the DHCP snippet is to be used for. Can not be set if node is set.
  - **`value`** (*string*, Optional): The new value of the DHCP snippet to be used in dhcpd.conf. Previous values are stored and can be reverted.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested reserved IP.
  
  Content type: `application/json`

  **HTTP 400 BAD REQUEST**
  
  IP is updated to a value belonging to another subnet. IP is updated to an IP already reserved.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to update the reserved IP.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested reserved IP range is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/dhcp-snippets/{id}/op-revert: Revert DHCP snippet to earlier version

  Revert the value of a DHCP snippet with the given id to an earlier revision.

  **Operation ID:** `DHCPSnippetHandler_revert`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A DHCP snippet id.

  **Request body (multipart/form-data):**

  - **`to`** (*integer*, Required): What revision in the DHCP snippet's history to revert to. This can either be an ID or a negative number representing how far back to go.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the reverted DHCP snippet.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested DHCP snippet is not found.
  
  Content type: `text/plain`

````

## DHCP Snippets (deprecated)

Operations for dhcp snippets (deprecated) resources.

````{dropdown} ~~GET /MAAS/api/2.0/dhcp-snippets/: List DHCP snippets~~

  List all available DHCP snippets.

  ```{warning}
  This endpoint is deprecated.
  ```

  **Operation ID:** `DHCPSnippetsHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of reserved IPs.
  
  Content type: `application/json`

````

````{dropdown} ~~POST /MAAS/api/2.0/dhcp-snippets/: Create a DHCP snippet~~

  Creates a DHCP snippet.

  ```{warning}
  This endpoint is deprecated.
  ```

  **Operation ID:** `DHCPSnippetsHandler_create`

  **Request body (multipart/form-data):**

  - **`description`** (*string*, Optional): A description of what the snippet does.
  - **`enabled`** (*boolean*, Optional): Whether or not the snippet is currently enabled.
  - **`global_snippet`** (*boolean*, Optional): Whether or not this snippet is to be applied globally. Cannot be used with node or subnet.
  - **`iprange`** (*string*, Optional): The iprange within a subnet this snippet applies to. Must also provide a subnet value.
  - **`name`** (*string*, Required): The name of the DHCP snippet.
  - **`node`** (*string*, Optional): The node this snippet applies to. Cannot be used with subnet or global_snippet.
  - **`subnet`** (*string*, Optional): The subnet this snippet applies to. Cannot be used with node or global_snippet.
  - **`value`** (*string*, Required): The snippet of config inserted into dhcpd.conf.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the reserved IP.
  
  Content type: `application/json`

  **HTTP 400 BAD REQUEST**
  
  IP parameter is required, and cannot be null or reserved. MAC address and VLAN need to be a unique together. IP needs to be within the subnet range. Subnet and VLAN for the reserved IP needs to be defined in MAAS.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to create the reserved IP.
  
  Content type: `text/plain`

````

## DNSResource

Operations for dnsresource resources.

````{dropdown} DELETE /MAAS/api/2.0/dnsresources/{id}/: Delete a DNS resource

  Delete a DNS resource with the given id.

  **Operation ID:** `DNSResourceHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The DNS resource id.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to update the requested DNS resource.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested DNS resource is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/dnsresources/{id}/: Read a DNS resource

  Read a DNS resource by id.

  **Operation ID:** `DNSResourceHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The DNS resource id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested DNS resource object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested DNS resource is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/dnsresources/{id}/: Update a DNS resource

  Update a DNS resource with the given id.

  **Operation ID:** `DNSResourceHandler_update`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The DNS resource id.

  **Request body (multipart/form-data):**

  - **`address_ttl`** (*string*, Optional): Default TTL for entries in this zone.
  - **`domain`** (*string*, Optional): Domain (name or id).
  - **`fqdn`** (*string*, Optional): Hostname (with domain) for the dnsresource. Either `fqdn` or `name` and `domain` must be specified. `fqdn` is ignored if either `name` or `domain` is given.
  - **`ip_addresses`** (*string*, Optional): Address (ip or id) to assign to the dnsresource. This creates an A or AAAA record, for each of the supplied ip_addresses, IPv4 or IPv6, respectively.
  - **`name`** (*string*, Optional): Hostname (without domain).

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated DNS resource object.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to update the requested DNS resource.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested DNS resource is not found.
  
  Content type: `text/plain`

````

## DNSResourceRecord

Operations for dnsresourcerecord resources.

````{dropdown} DELETE /MAAS/api/2.0/dnsresourcerecords/{id}/: Delete a DNS resource record

  Delete a DNS resource record with the given id.

  **Operation ID:** `DNSResourceRecordHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The DNS resource record id.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to delete the requested DNS resource record.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested DNS resource record is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/dnsresourcerecords/{id}/: Read a DNS resource record description Read a DNS resource record with the given id.

  Manage dnsresourcerecord.

  **Operation ID:** `DNSResourceRecordHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The DNS resource record id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested DNS resource object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested DNS resource record was not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/dnsresourcerecords/{id}/: Update a DNS resource record

  Update a DNS resource record with the given id.

  **Operation ID:** `DNSResourceRecordHandler_update`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The DNS resource record id.

  **Request body (multipart/form-data):**

  - **`rrdata`** (*string*, Optional): Resource data (everything to the right of type.)
  - **`rrtype`** (*string*, Optional): Resource type.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated DNS resource record object.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to update the requested DNS resource record.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested DNS resource record is not found.
  
  Content type: `text/plain`

````

## DNSResourceRecords

Operations for dnsresourcerecords resources.

````{dropdown} GET /MAAS/api/2.0/dnsresourcerecords/: List all DNS resource records

  List all DNS resource records.

  **Operation ID:** `DNSResourceRecordsHandler_read`

  **Parameters:**

  - **`fqdn`** (*string*, Optional): Restricts the listing to entries for the fqdn.
  - **`domain`** (*string*, Optional): Restricts the listing to entries for the domain.
  - **`name`** (*string*, Optional): Restricts the listing to entries of the given name.
  - **`rrtype`** (*string*, Optional): Restricts the listing to entries which have records of the given rrtype.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of the requested DNS resource record objects.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/dnsresourcerecords/: Create a DNS resource record

  Create a new DNS resource record.

  **Operation ID:** `DNSResourceRecordsHandler_create`

  **Request body (multipart/form-data):**

  - **`domain`** (*string*, Optional): The domain (name or id) where to create the DNS resource record (Domain (e.g. 'maas')
  - **`fqdn`** (*string*, Optional): Hostname (with domain) for the dnsresource. Either `fqdn` or `name` and `domain` must be specified. `fqdn` is ignored if either name or domain is given (e.g. www.your-maas.maas).
  - **`name`** (*string*, Optional): The name (or hostname without a domain) of the DNS resource record (e.g. www.your-maas)
  - **`rrdata`** (*string*, Optional): The resource record data (e.g. 'your-maas', '10 mail.your-maas.maas')
  - **`rrtype`** (*string*, Optional): The resource record type (e.g `cname`, `mx`, `ns`, `srv`, `sshfp`, `txt`).

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new DNS resource record object.
  
  Content type: `application/json`

````

## DNSResources

Operations for dnsresources resources.

````{dropdown} GET /MAAS/api/2.0/dnsresources/: List resources

  List all resources for the specified criteria.

  **Operation ID:** `DNSResourcesHandler_read`

  **Parameters:**

  - **`fqdn`** (*string*, Optional): Restricts the listing to entries for the fqdn.
  - **`domain`** (*string*, Optional): Restricts the listing to entries for the domain.
  - **`name`** (*string*, Optional): Restricts the listing to entries of the given name.
  - **`rrtype`** (*string*, Optional): Restricts the listing to entries which have records of the given rrtype.
  - **`all`** (*boolean*, Optional): Include implicit DNS records created for nodes registered in MAAS if true.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of the requested DNS resource objects.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested DNS resources are not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/dnsresources/: Create a DNS resource

  Create a DNS resource.

  **Operation ID:** `DNSResourcesHandler_create`

  **Request body (multipart/form-data):**

  - **`address_ttl`** (*string*, Optional): Default TTL for entries in this zone.
  - **`domain`** (*string*, Required): Domain (name or id).
  - **`fqdn`** (*string*, Optional): Hostname (with domain) for the dnsresource. Either `fqdn` or `name` and `domain` must be specified. `fqdn` is ignored if either `name` or `domain` is given.
  - **`ip_addresses`** (*string*, Optional): Address (ip or id) to assign to the dnsresource. This creates an A or AAAA record, for each of the supplied ip_addresses, IPv4 or IPv6, respectively.
  - **`name`** (*string*, Required): Hostname (without domain).

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new DNS resource object.
  
  Content type: `application/json`

````

## Device

Operations for device resources.

````{dropdown} DELETE /MAAS/api/2.0/devices/{system_id}/: Delete a device

  Delete a device with the given system_id.

  **Operation ID:** `DeviceHandler_delete`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A device system_id.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions required to delete the device.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested device is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/devices/{system_id}/: Read a node

  Reads a node with the given system_id.

  **Operation ID:** `DeviceHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A node's system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the requested node.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/devices/{system_id}/: Update a device

  Update a device with a given system_id.

  **Operation ID:** `DeviceHandler_update`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A device system_id.

  **Request body (multipart/form-data):**

  - **`description`** (*string*, Optional): The optional description for this machine.
  - **`domain`** (*string*, Optional): The domain for this device.
  - **`hostname`** (*string*, Optional): The hostname for this device.
  - **`parent`** (*string*, Optional): Optional system_id to indicate this device's parent. If the parent is already set and this parameter is omitted, the parent will be unchanged.
  - **`zone`** (*string*, Optional): Name of a valid physical zone in which to place this node.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated device.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions required to update the device.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested device is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/devices/{system_id}/op-details: Get system details

  Returns system details - for example, LLDP and `lshw` XML dumps.
Returns a `{detail_type: xml, .}` map, where `detail_type` is something like "lldp" or "lshw".
Note that this is returned as BSON and not JSON. This is for efficiency, but mainly because JSON can't do binary content without applying additional encoding like base-64. The example output below is represented in ASCII using `bsondump example.bson` and is for demonstrative purposes.

  **Operation ID:** `DeviceHandler_details`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The node's system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A BSON object represented here in ASCII using `bsondump example.bson`.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to see the node details.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/devices/{system_id}/op-power_parameters: Get power parameters

  Gets power parameters for a given system_id, if any. For some types of power control this will include private information such as passwords and secret keys.
Note that this method is reserved for admin users and returns a 403 if the user is not one.

  **Operation ID:** `DeviceHandler_power_parameters`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 

  **Responses:**

  **HTTP 200 OK**
  
  200

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to see the power parameters.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/devices/{system_id}/op-restore_default_configuration: Reset device configuration

  Restore the configuration options of a device with the given system_id to default values.

  **Operation ID:** `DeviceHandler_restore_default_configuration`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A device system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated device.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions required to update the device.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested device is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/devices/{system_id}/op-restore_networking_configuration: Reset networking options

  Restore the networking options of a device with the given system_id to default values.

  **Operation ID:** `DeviceHandler_restore_networking_configuration`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A device system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated device.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions required to update the device.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested device is not found.
  
  Content type: `text/plain`

````

````{dropdown} ~~POST /MAAS/api/2.0/devices/{system_id}/op-set_owner_data: Deprecated, use set-workload-annotations.~~

  Deprecated, use set-workload-annotations instead.

  ```{warning}
  This endpoint is deprecated.
  ```

  **Operation ID:** `DeviceHandler_set_owner_data`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The user does not have set the zone.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/devices/{system_id}/op-set_workload_annotations: Set key=value data

  Set key=value data for the current owner.
Pass any key=value form data to this method to add, modify, or remove.
A key is removed when the value for that key is set to an empty string.
This operation will not remove any previous keys unless explicitly passed with an empty string. All workload annotations are removed when the machine is no longer allocated to a user.

  **Operation ID:** `DeviceHandler_set_workload_annotations`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 

  **Request body (multipart/form-data):**

  - **`key`** (*string*, Required): `key` can be any string value.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The user does not have set the zone.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

## Devices

Operations for devices resources.

````{dropdown} GET /MAAS/api/2.0/devices/: List Nodes visible to the user

  List nodes visible to current user, optionally filtered by criteria.
Nodes are sorted by id (i.e. most recent last) and grouped by type.

  **Operation ID:** `DevicesHandler_read`

  **Parameters:**

  - **`hostname`** (*string*, Optional): Only nodes relating to the node with the matching hostname will be returned. This can be specified multiple times to see multiple nodes.
  - **`cpu_count`** (*integer*, Optional): Only nodes with the specified minimum number of CPUs will be included.
  - **`mem`** (*string*, Optional): Only nodes with the specified minimum amount of RAM (in MiB) will be included.
  - **`mac_address`** (*string*, Optional): Only nodes relating to the node owning the specified MAC address will be returned. This can be specified multiple times to see multiple nodes.
  - **`id`** (*string*, Optional): Only nodes relating to the nodes with matching system ids will be returned.
  - **`domain`** (*string*, Optional): Only nodes relating to the nodes in the domain will be returned.
  - **`zone`** (*string*, Optional): Only nodes relating to the nodes in the zone will be returned.
  - **`pool`** (*string*, Optional): Only nodes belonging to the pool will be returned.
  - **`agent_name`** (*string*, Optional): Only nodes relating to the nodes with matching agent names will be returned.
  - **`fabrics`** (*string*, Optional): Only nodes with interfaces in specified fabrics will be returned.
  - **`not_fabrics`** (*string*, Optional): Only nodes with interfaces not in specified fabrics will be returned.
  - **`vlans`** (*string*, Optional): Only nodes with interfaces in specified VLANs will be returned.
  - **`not_vlans`** (*string*, Optional): Only nodes with interfaces not in specified VLANs will be returned.
  - **`subnets`** (*string*, Optional): Only nodes with interfaces in specified subnets will be returned.
  - **`not_subnets`** (*string*, Optional): Only nodes with interfaces not in specified subnets will be returned.
  - **`link_speed`** (*string*, Optional): Only nodes with interfaces with link speeds greater than or equal to link_speed will be returned.
  - **`status`** (*string*, Optional): Only nodes with specified status will be returned.
  - **`pod`** (*string*, Optional): Only nodes that belong to a specified pod will be returned.
  - **`not_pod`** (*string*, Optional): Only nodes that don't belong to a specified pod will be returned.
  - **`pod_type`** (*string*, Optional): Only nodes that belong to a pod of the specified type will be returned.
  - **`not_pod_type`** (*string*, Optional): Only nodes that don't belong to a pod of the specified type will be returned.
  - **`devices`** (*string*, Optional): Only return nodes which have one or more devices containing the following constraints in the format key=value[,key2=value2[,.] Each key can be one of the following: - `vendor_id`: The device vendor id - `product_id`: The device product id - `vendor_name`: The device vendor name, not case sensative - `product_name`: The device product name, not case sensative - `commissioning_driver`: The device uses this driver during commissioning.
  - **`arch`** (*string*, Optional): Only nodes with the specified architecture will be returned.
  - **`not_arch`** (*string*, Optional): Only nodes without the specified architecture will be returned.
  - **`cpu_speed`** (*string*, Optional): Only nodes with CPUs running at the specified speed (in MHz) will be returned.
  - **`deployment_target`** (*string*, Optional): Only nodes with the specified deployment target will be returned.
  - **`not_deployment_target`** (*string*, Optional): Only nodes without the specified deployment target will be returned.
  - **`fabric_classes`** (*string*, Optional): Attached to fabric with specified classes.
  - **`not_fabric_classes`** (*string*, Optional): Not attached to fabric with specified classes.
  - **`interfaces`** (*string*, Optional): Only nodes with interfaces matching the specified constraints will be returned.
  - **`not_hostname`** (*string*, Optional): Hostnames to ignore.
  - **`not_id`** (*string*, Optional): System IDs to ignore.
  - **`not_domain`** (*string*, Optional): Domain names to ignore.
  - **`not_agent_name`** (*string*, Optional): Excludes nodes with events matching the agent name.
  - **`not_in_pool`** (*string*, Optional): Only nodes not in the specified resource pools will be returned.
  - **`not_in_zone`** (*string*, Optional): Not in zone.
  - **`not_owner`** (*string*, Optional): Only nodes not owned by the specified users will be returned.
  - **`not_power_state`** (*string*, Optional): Only nodes not in the specified power states will be returned.
  - **`not_simple_status`** (*string*, Optional): Exclude nodes with the specified simplified status.
  - **`not_status`** (*string*, Optional): Exclude nodes with the specified status.
  - **`not_tags`** (*string*, Optional): Not having tags.
  - **`owner`** (*string*, Optional): Only nodes owned by the specified users will be returned.
  - **`power_state`** (*string*, Optional): Only nodes in the specified power states will be returned.
  - **`simple_status`** (*string*, Optional): Only includes nodes with the specified simplified status.
  - **`storage`** (*string*, Optional): Only nodes with storage matching the specified constraints will be returned.
  - **`system_id`** (*string*, Optional): Only nodes with the specified system IDs will be returned.
  - **`tags`** (*string*, Optional): Only nodes with the specified tags will be returned.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of node objects.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/devices/: Create a new device

  Create a new device.

  **Operation ID:** `DevicesHandler_create`

  **Request body (multipart/form-data):**

  - **`description`** (*string*, Optional): A optional description.
  - **`domain`** (*string*, Optional): The domain of the device. If not given the default domain is used.
  - **`hostname`** (*string*, Optional): A hostname. If not given, one will be generated.
  - **`mac_addresses`** (*string*, Required): One or more MAC addresses for the device.
  - **`parent`** (*string*, Optional): The system id of the parent.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new device.
  
  Content type: `application/json`

  **HTTP 400 BAD REQUEST**
  
  There was a problem with the given parameters.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/devices/op-is_registered: MAC address registered

  Returns whether or not the given MAC address is registered within this MAAS (and attached to a non-retired node).

  **Operation ID:** `DevicesHandler_is_registered`

  **Parameters:**

  - **`mac_address`** (*object*, Required): The MAC address to be checked.

  **Responses:**

  **HTTP 200 OK**
  
  'true' or 'false'

  **HTTP 400 BAD REQUEST**
  
  mac_address was missing
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/devices/op-set_zone: Assign nodes to a zone

  Assigns a given node to a given zone.

  **Operation ID:** `DevicesHandler_set_zone`

  **Request body (multipart/form-data):**

  - **`nodes`** (*string*, Required): The node to add.
  - **`zone`** (*string*, Required): The zone name.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 400 BAD REQUEST**
  
  The given parameters were not correct.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user does not have set the zone.
  
  Content type: `text/plain`

````

## Discoveries

Operations for discoveries resources.

````{dropdown} GET /MAAS/api/2.0/discovery/: List all discovered devices

  Lists all the devices MAAS has discovered. Discoveries are listed in the order they were last observed on the network (most recent first).

  **Operation ID:** `DiscoveriesHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of all previously discovered devices.
  
  Content type: `application/json`

````

````{dropdown} GET /MAAS/api/2.0/discovery/op-by_unknown_ip: List all discovered devices with an unknown IP address

  Lists all discovered devices with an unknown IP address.
Filters the list of discovered devices by excluding any discoveries where a known MAAS node is configured with the IP address of a discovery, or has been observed using it after it was assigned by a MAAS-managed DHCP server.
Discoveries are listed in the order they were last observed on the network (most recent first).

  **Operation ID:** `DiscoveriesHandler_by_unknown_ip`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of all previously discovered devices with unknown IP addresses.
  
  Content type: `application/json`

````

````{dropdown} GET /MAAS/api/2.0/discovery/op-by_unknown_ip_and_mac: Lists all discovered devices completely unknown to MAAS

  Lists all discovered devices completely unknown to MAAS.
Filters the list of discovered devices by excluding any discoveries where a known MAAS node is configured with either the MAC address or the IP address of a discovery.
Discoveries are listed in the order they were last observed on the network (most recent first).

  **Operation ID:** `DiscoveriesHandler_by_unknown_ip_and_mac`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of all previously discovered devices with unknown MAC and IP addresses.
  
  Content type: `application/json`

````

````{dropdown} GET /MAAS/api/2.0/discovery/op-by_unknown_mac: List all discovered devices with unknown MAC

  Filters the list of discovered devices by excluding any discoveries where an interface known to MAAS is configured with a discovered MAC address.
Discoveries are listed in the order they were last observed on the network (most recent first).

  **Operation ID:** `DiscoveriesHandler_by_unknown_mac`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of all previously discovered devices with unknown MAC addresses.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/discovery/op-clear: Delete all discovered neighbours

  Deletes all discovered neighbours and/or mDNS entries.
Note: One of `mdns`, `neighbours`, or `all` parameters must be supplied.

  **Operation ID:** `DiscoveriesHandler_clear`

  **Request body (multipart/form-data):**

  - **`all`** (*boolean*, Optional): Delete all discovery data.
  - **`mdns`** (*boolean*, Optional): Delete all mDNS entries.
  - **`neighbours`** (*boolean*, Optional): Delete all neighbour entries.

  **Responses:**

  **HTTP 200 OK**
  
  204

````

````{dropdown} POST /MAAS/api/2.0/discovery/op-clear_by_mac_and_ip: Delete discoveries that match a MAC and IP

  Deletes all discovered neighbours (and associated reverse DNS entries) associated with the given IP address and MAC address.

  **Operation ID:** `DiscoveriesHandler_clear_by_mac_and_ip`

  **Request body (multipart/form-data):**

  - **`ip`** (*string*, Required): IP address
  - **`mac`** (*string*, Required): MAC address

  **Responses:**

  **HTTP 200 OK**
  
  204

````

````{dropdown} POST /MAAS/api/2.0/discovery/op-scan: Run discovery scan on rack networks

  Immediately run a neighbour discovery scan on all rack networks.
This command causes each connected rack controller to execute the 'maas-rack scan-network' command, which will scan all CIDRs configured on the rack controller using 'nmap' (if it is installed) or 'ping'.
Network discovery must not be set to 'disabled' for this command to be useful.
Scanning will be started in the background, and could take a long time on rack controllers that do not have 'nmap' installed and are connected to large networks.
If the call is a success, this method will return a dictionary of results with the following keys:
`result`: A human-readable string summarizing the results.
`scan_attempted_on`: A list of rack system_id values where a scan was attempted. (That is, an RPC connection was successful and a subsequent call was intended.) `failed_to_connect_to`: A list of rack system_id values where the RPC connection failed.
`scan_started_on`: A list of rack system_id values where a scan was successfully started.
`scan_failed_on`: A list of rack system_id values where a scan was attempted, but failed because a scan was already in progress.
`rpc_call_timed_out_on`: A list of rack system_id values where the RPC connection was made, but the call timed out before a ten second timeout elapsed.

  **Operation ID:** `DiscoveriesHandler_scan`

  **Request body (multipart/form-data):**

  - **`always_use_ping`** (*string*, Optional): If True, will force the scan to use 'ping' even if 'nmap' is installed. Default: False.
  - **`cidr`** (*string*, Optional): The subnet CIDR(s) to scan (can be specified multiple times). If not specified, defaults to all networks.
  - **`force`** (*boolean*, Optional): If True, will force the scan, even if all networks are specified. (This may not be the best idea, depending on acceptable use agreements, and the politics of the organization that owns the network.) Note that this parameter is required if all networks are specified. Default: False.
  - **`slow`** (*string*, Optional): If True, and 'nmap' is being used, will limit the scan to nine packets per second. If the scanner is 'ping', this option has no effect. Default: False.
  - **`threads`** (*string*, Optional): The number of threads to use during scanning. If 'nmap' is the scanner, the default is one thread per 'nmap' process. If 'ping' is the scanner, the default is four threads per CPU.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a dictionary of results.
  
  Content type: `application/json`

````

## Discovery

Operations for discovery resources.

````{dropdown} GET /MAAS/api/2.0/discovery/{discovery_id}/: Read a discovery

  Read a discovery with the given discovery_id.

  **Operation ID:** `DiscoveryHandler_read`

  **Parameters:**

  - **`{discovery_id}`** (*string*, path parameter, Required): 
  - **`{discovery_id`** (*string*, Required): A discovery_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested discovery.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested discovery is not found.
  
  Content type: `text/plain`

````

## Domain

Operations for domain resources.

````{dropdown} DELETE /MAAS/api/2.0/domains/{id}/: Delete domain

  Delete a domain with the given id.

  **Operation ID:** `DomainHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A domain id.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions required to update the domain.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested domain name is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/domains/{id}/: Read domain

  Read a domain with the given id.

  **Operation ID:** `DomainHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A domain id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the requsted domain.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested domain is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/domains/{id}/: Update a domain

  Update a domain with the given id.

  **Operation ID:** `DomainHandler_update`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A domain id.

  **Request body (multipart/form-data):**

  - **`authoritative`** (*string*, Optional): True if we are authoritative for this domain.
  - **`forward_dns_servers`** (*string*, Optional): List of IP addresses for forward DNS servers when MAAS is not authoritative for this domain.
  - **`name`** (*string*, Required): Name of the domain.
  - **`ttl`** (*string*, Optional): The default TTL for this domain.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the updated domain.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions required to update the domain.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested domain name is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/domains/{id}/op-set_default: Set domain as default

  Set the specified domain to be the default.

  **Operation ID:** `DomainHandler_set_default`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A domain id. If any unallocated nodes are using the previous default domain, changes them to use the new default domain.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the updated domain.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions required to update the domain.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested domain name is not found.
  
  Content type: `text/plain`

````

## Domains

Operations for domains resources.

````{dropdown} GET /MAAS/api/2.0/domains/: List all domains

  List all domains.

  **Operation ID:** `DomainsHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of domain objects.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/domains/: Create a domain

  Create a domain.

  **Operation ID:** `DomainsHandler_create`

  **Request body (multipart/form-data):**

  - **`authoritative`** (*string*, Optional): Class type of the domain.
  - **`forward_dns_servers`** (*string*, Optional): List of forward dns server IP addresses when MAAS is not authorititative.
  - **`name`** (*string*, Required): Name of the domain.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new domain object.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/domains/op-set_serial: Set the SOA serial number

  Set the SOA serial number for all DNS zones.

  **Operation ID:** `DomainsHandler_set_serial`

  **Request body (multipart/form-data):**

  - **`serial`** (*integer*, Required): Serial number to use next.

  **Responses:**

  **HTTP 200 OK**
  
  No content returned.
  
  Content type: `text/plain`

````

## Events

Operations for events resources.

````{dropdown} GET /MAAS/api/2.0/events/op-query: List node events

  List node events, optionally filtered by various criteria via URL query parameters.

  **Operation ID:** `EventsHandler_query`

  **Parameters:**

  - **`hostname`** (*string*, Optional): An optional hostname. Only events relating to the node with the matching hostname will be returned. This can be specified multiple times to get events relating to more than one node.
  - **`mac_address`** (*string*, Optional): An optional list of MAC addresses. Only nodes with matching MAC addresses will be returned.
  - **`id`** (*string*, Optional): An optional list of system ids. Only nodes with matching system ids will be returned.
  - **`zone`** (*string*, Optional): An optional name for a physical zone. Only nodes in the zone will be returned.
  - **`agent_name`** (*string*, Optional): An optional agent name. Only nodes with matching agent names will be returned.
  - **`level`** (*string*, Optional): Desired minimum log level of returned events. Returns this level of events and greater. Choose from: AUDIT, CRITICAL, DEBUG, ERROR, INFO, WARNING. The default is INFO.
  - **`limit`** (*string*, Optional): Optional number of events to return. Default 100. Maximum: 1000.
  - **`before`** (*string*, Optional): Optional event id. Defines where to start returning older events.
  - **`after`** (*string*, Optional): Optional event id. Defines where to start returning newer events.
  - **`owner`** (*string*, Optional): If specified, filters the list to show only events owned by the specified username.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of events objects.
  
  Content type: `application/json`

````

## Fabric

Operations for fabric resources.

````{dropdown} DELETE /MAAS/api/2.0/fabrics/{id}/: Delete a fabric

  Delete a fabric with the given id.

  **Operation ID:** `FabricHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A fabric id.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested fabric is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/fabrics/{id}/: Read a fabric

  Read a fabric with the given id.

  **Operation ID:** `FabricHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A fabric id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested fabric object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested fabric is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/fabrics/{id}/: Update fabric

  Update a fabric with the given id.

  **Operation ID:** `FabricHandler_update`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A fabric id.

  **Request body (multipart/form-data):**

  - **`class_type`** (*string*, Optional): Class type of the fabric.
  - **`description`** (*string*, Optional): Description of the fabric.
  - **`name`** (*string*, Optional): Name of the fabric.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated fabric object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested fabric is not found.
  
  Content type: `text/plain`

````

## Fabrics

Operations for fabrics resources.

````{dropdown} GET /MAAS/api/2.0/fabrics/: List fabrics

  List all fabrics.

  **Operation ID:** `FabricsHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of fabric objects.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/fabrics/: Create a fabric

  Create a fabric.

  **Operation ID:** `FabricsHandler_create`

  **Request body (multipart/form-data):**

  - **`class_type`** (*string*, Optional): Class type of the fabric.
  - **`description`** (*string*, Optional): Description of the fabric.
  - **`name`** (*string*, Optional): Name of the fabric.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new fabric object.
  
  Content type: `application/json`

````

## File

Operations for file resources.

````{dropdown} DELETE /MAAS/api/2.0/files/{filename}/: Delete a file

  Delete a file with the given file name.

  **Operation ID:** `FileHandler_delete`

  **Parameters:**

  - **`{filename}`** (*string*, path parameter, Required): 
  - **`{filename}`** (*string*, path parameter, Required): The name of the file.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested file is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/files/{filename}/: Read a stored file

  Reads a stored file with the given file name.
The content of the file is base64-encoded.

  **Operation ID:** `FileHandler_read`

  **Parameters:**

  - **`{filename}`** (*string*, path parameter, Required): 
  - **`{filename}`** (*string*, path parameter, Required): The name of the file.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested file.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested file is not found.
  
  Content type: `text/plain`

````

## Files

Operations for files resources.

````{dropdown} DELETE /MAAS/api/2.0/files/: Delete a file

  Delete a stored file.

  **Operation ID:** `FilesHandler_delete`

  **Parameters:**

  - **`filename`** (*string*, Required): The filename of the object to be deleted.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested file is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/files/: List files

  List the files from the file storage.
The returned files are ordered by file name and the content is excluded.

  **Operation ID:** `FilesHandler_read`

  **Parameters:**

  - **`prefix`** (*string*, Optional): Prefix used to filter returned files.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of the reqeusted file names.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/files/: Add a new file

  Add a new file to the file storage.

  **Operation ID:** `FilesHandler_create`

  **Request body (multipart/form-data):**

  - **`file`** (*string*, Required): File data. Content type must be `application/octet-stream`.
  - **`filename`** (*string*, Required): The file name to use in storage.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new file.
  
  Content type: `application/json`

  **HTTP 400 BAD REQUEST**
  
  The filename is missing, the file data is missing or more than one file is supplied.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/files/op-get: Get a named file

  Get a named file from the file storage.

  **Operation ID:** `FilesHandler_get`

  **Parameters:**

  - **`filename`** (*string*, Required): The name of the file.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested file.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested file is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/files/op-get_by_key: Get a file by key

  Get a file from the file storage with the given key.

  **Operation ID:** `FilesHandler_get_by_key`

  **Parameters:**

  - **`key`** (*string*, Required): The file's key.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested file.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested file is not found.
  
  Content type: `text/plain`

````

## IP Addresses

Operations for ip addresses resources.

````{dropdown} GET /MAAS/api/2.0/ipaddresses/: List IP addresses

  List all IP addresses known to MAAS.
By default, gets a listing of all IP addresses allocated to the requesting user.

  **Operation ID:** `IPAddressesHandler_read`

  **Parameters:**

  - **`ip`** (*string*, Optional): If specified, will only display information for the specified IP address.
  - **`all`** (*boolean*, Optional): (Admin users only) If True, all reserved IP addresses will be shown. (By default, only addresses of type 'User reserved' that are assigned to the requesting user are shown.)
  - **`owner`** (*string*, Optional): (Admin users only) If specified, filters the list to show only IP addresses owned by the specified username.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of IP address objects.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/ipaddresses/op-release: Release an IP address

  Release an IP address that was previously reserved by the user.

  **Operation ID:** `IPAddressesHandler_release`

  **Request body (multipart/form-data):**

  - **`discovered`** (*boolean*, Optional): If True, allows a MAAS administrator to release a discovered address. Only valid if 'force' is specified. If not specified, MAAS will attempt to release any type of address except for discovered addresses.
  - **`force`** (*boolean*, Optional): If True, allows a MAAS administrator to force an IP address to be released, even if it is not a user-reserved IP address or does not belong to the requesting user. Use with caution.
  - **`ip`** (*string*, Required): The IP address to release.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested IP address is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/ipaddresses/op-reserve: Reserve an IP address

  Reserve an IP address for use outside of MAAS.
Returns an IP adddress that MAAS will not allow any of its known nodes to use; it is free for use by the requesting user until released by the user.
The user must supply either a subnet or a specific IP address within a subnet.

  **Operation ID:** `IPAddressesHandler_reserve`

  **Request body (multipart/form-data):**

  - **`hostname`** (*string*, Optional): The hostname to use for the specified IP address. If no domain component is given, the default domain will be used.
  - **`ip`** (*string*, Optional): The IP address, which must be within a known subnet.
  - **`ip_address`** (*string*, Optional): (Deprecated.) Alias for 'ip' parameter. Provided for backward compatibility.
  - **`mac`** (*string*, Optional): The MAC address that should be linked to this reservation.
  - **`subnet`** (*string*, Optional): CIDR representation of the subnet on which the IP reservation is required. E.g. 10.1.2.0/24

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the reserved IP.
  
  Content type: `application/json`

  **HTTP 400 BAD REQUEST**
  
  No subnet in MAAS matching the provided one, or an ip_address was supplied, but a corresponding subnet could not be found.
  
  Content type: `text/plain`

  **HTTP 503 SERVICE UNAVAILABLE**
  
  No more IP addresses are available.
  
  Content type: `text/plain`

````

## IP Range

Operations for ip range resources.

````{dropdown} DELETE /MAAS/api/2.0/ipranges/{id}/: Delete an IP range

  Delete an IP range with the given id.

  **Operation ID:** `IPRangeHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): An IP range id.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions required to delete the IP range.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested IP range is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/ipranges/{id}/: Read an IP range

  Read an IP range with the given id.

  **Operation ID:** `IPRangeHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): An IP range id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested IP range.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested IP range is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/ipranges/{id}/: Update an IP range

  Update an IP range with the given id.

  **Operation ID:** `IPRangeHandler_update`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): An IP range id.

  **Request body (multipart/form-data):**

  - **`comment`** (*string*, Optional): A description of this range. (optional)
  - **`end_ip`** (*string*, Optional): End IP address of this range (inclusive).
  - **`start_ip`** (*string*, Optional): Start IP address of this range (inclusive).

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested IP range.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions required to update the IP range.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested IP range is not found.
  
  Content type: `text/plain`

````

## IP Ranges

Operations for ip ranges resources.

````{dropdown} GET /MAAS/api/2.0/ipranges/: List all IP ranges

  List all available IP ranges.

  **Operation ID:** `IPRangesHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of IP ranges.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/ipranges/: Create an IP range

  Create a new IP range.

  **Operation ID:** `IPRangesHandler_create`

  **Request body (multipart/form-data):**

  - **`comment`** (*string*, Optional): A description of this range.
  - **`end_ip`** (*string*, Required): End IP address of this range (inclusive).
  - **`start_ip`** (*string*, Required): Start IP address of this range (inclusive).
  - **`subnet`** (*integer*, Required): Subnet associated with this range.
  - **`type`** (*string*, Required): Type of this range. (`dynamic` or `reserved`)

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new IP range.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions required to create an IP range.
  
  Content type: `text/plain`

````

## Interface

Operations for interface resources.

````{dropdown} DELETE /MAAS/api/2.0/nodes/{system_id}/interfaces/{id}/: Delete an interface

  Delete an interface with the given system_id and interface id.

  **Operation ID:** `InterfaceHandler_delete`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A system_id.
  - **`{id}`** (*integer*, path parameter, Required): An interface id.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested machine or interface is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/interfaces/{id}/: Read an interface

  Read an interface with the given system_id and interface id.

  **Operation ID:** `InterfaceHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A system_id.
  - **`{id}`** (*integer*, path parameter, Required): An interface id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new requested interface object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine or interface is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/nodes/{system_id}/interfaces/{id}/: Update an interface

  Update an interface with the given system_id and interface id.
Note: machines must have a status of Ready or Broken to have access to all options. Machines with Deployed status can only have the name and/or mac_address updated for an interface. This is intented to allow a bad interface to be replaced while the machine remains deployed.

  **Operation ID:** `InterfaceHandler_update`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A system_id.
  - **`{id}`** (*integer*, path parameter, Required): An interface id.

  **Request body (multipart/form-data):**

  - **`accept_ra`** (*string*, Optional): Accept router advertisements. (IPv6 only)
  - **`bond_downdelay`** (*integer*, Optional): (Bonds) Specifies the time, in milliseconds, to wait before disabling a slave after a link failure has been detected.
  - **`bond_lacp_rate`** (*string*, Optional): (Bonds) Option specifying the rate in which we'll ask our link partner to transmit LACPDU packets in 802.3ad mode. Available options are `fast` or `slow`. (Default: `slow`).
  - **`bond_miimon`** (*integer*, Optional): (Bonds) The link monitoring freqeuncy in milliseconds. (Default: 100).
  - **`bond_mode`** (*string*, Optional): (Bonds) The operating mode of the bond. (Default: `active-backup`). Supported bonding modes (bond-mode): - `balance-rr`: Transmit packets in sequential order from the first available slave through the last. This mode provides load balancing and fault tolerance. - `active-backup`: Only one slave in the bond is active. A different slave becomes active if, and only if, the active slave fails. The bond's MAC address is externally visible on only one port (network adapter) to avoid confusing the switch. - `balance-xor`: Transmit based on the selected transmit hash policy. The default policy is a simple [(source MAC address XOR'd with destination MAC address XOR packet type ID) modulo slave count]. - `broadcast`: Transmits everything on all slave interfaces. This mode provides fault tolerance. - `802.3ad`: IEEE 802.3ad Dynamic link aggregation. Creates aggregation groups that share the same speed and duplex settings. Utilizes all slaves in the active aggregator according to the 802.3ad specification. - `balance-tlb`: Adaptive transmit load balancing: channel bonding that does not require any special switch support. - `balance-alb`: Adaptive load balancing: includes balance-tlb plus receive load balancing (rlb) for IPV4 traffic, and does not require any special switch support. The receive load balancing is achieved by ARP negotiation.
  - **`bond_updelay`** (*integer*, Optional): (Bonds) Specifies the time, in milliseconds, to wait before enabling a slave after a link recovery has been detected.
  - **`bond_xmit_hash_policy`** (*string*, Optional): (Bonds) The transmit hash policy to use for slave selection in balance-xor, 802.3ad, and tlb modes. Possible values are: `layer2`, `layer2+3`, `layer3+4`, `encap2+3`, `encap3+4`.
  - **`bridge_fd`** (*integer*, Optional): (Bridge interfaces) Set bridge forward delay to time seconds. (Default: 15).
  - **`bridge_stp`** (*boolean*, Optional): (Bridge interfaces) Turn spanning tree protocol on or off. (Default: False).
  - **`bridge_type`** (*string*, Optional): (Bridge interfaces) Type of bridge to create. Possible values are: `standard`, `ovs`.
  - **`interface_speed`** (*integer*, Optional): (Physical interfaces) The speed of the interface in Mbit/s. (Default: 0).
  - **`link_connected`** (*boolean*, Optional): (Physical interfaces) Whether or not the interface is physically conntected to an uplink. (Default: True).
  - **`link_speed`** (*integer*, Optional): (Physical interfaces) The speed of the link in Mbit/s. (Default: 0).
  - **`mac_address`** (*string*, Optional): (Bridge interfaces) MAC address of the interface.
  - **`mtu`** (*string*, Optional): Maximum transmission unit.
  - **`name`** (*string*, Optional): (Bridge interfaces) Name of the interface.
  - **`parent`** (*integer*, Optional): (Bridge interfaces) Parent interface ids for this bridge interface.
  - **`parents`** (*integer*, Optional): (Bond interfaces) Parent interface ids that make this bond.
  - **`tags`** (*string*, Optional): (Bridge interfaces) Tags for the interface.
  - **`vlan`** (*integer*, Optional): (Bridge interfaces) VLAN id the interface is connected to.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new requested interface object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine or interface is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/interfaces/{id}/op-add_tag: Add a tag to an interface

  Add a tag to an interface with the given system_id and interface id.

  **Operation ID:** `InterfaceHandler_add_tag`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A system_id.
  - **`{id}`** (*integer*, path parameter, Required): An interface id.

  **Request body (multipart/form-data):**

  - **`tag`** (*string*, Optional): The tag to add.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated interface object.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  If the user does not have the permission to add a tag.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine or interface is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/interfaces/{id}/op-disconnect: Disconnect an interface

  Disconnect an interface with the given system_id and interface id.
Deletes any linked subnets and IP addresses, and disconnects the interface from any associated VLAN.

  **Operation ID:** `InterfaceHandler_disconnect`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated interface object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine or interface is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/interfaces/{id}/op-link_subnet: Link interface to a subnet

  Link an interface with the given system_id and interface id to a subnet.

  **Operation ID:** `InterfaceHandler_link_subnet`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A system_id.
  - **`{id}`** (*integer*, path parameter, Required): An interface id.

  **Request body (multipart/form-data):**

  - **`default_gateway`** (*string*, Optional): True sets the gateway IP address for the subnet as the default gateway for the node this interface belongs to. Option can only be used with the `AUTO` and `STATIC` modes.
  - **`force`** (*boolean*, Optional): If True, allows `LINK_UP` to be set on the interface even if other links already exist. Also allows the selection of any VLAN, even a VLAN MAAS does not believe the interface to currently be on. Using this option will cause all other links on the interface to be deleted. (Defaults to False.)
  - **`ip_address`** (*string*, Optional): IP address for the interface in subnet. Only used when mode is `STATIC`. If not provided an IP address from subnet will be auto selected.
  - **`mode`** (*string*, Required): `AUTO`, `DHCP`, `STATIC` or `LINK_UP` connection to subnet. Mode definitions: - `AUTO`: Assign this interface a static IP address from the provided subnet. The subnet must be a managed subnet. The IP address will not be assigned until the node goes to be deployed. - `DHCP`: Bring this interface up with DHCP on the given subnet. Only one subnet can be set to `DHCP`. If the subnet is managed this interface will pull from the dynamic IP range. - `STATIC`: Bring this interface up with a static IP address on the given subnet. Any number of static links can exist on an interface. - `LINK_UP`: Bring this interface up only on the given subnet. No IP address will be assigned to this interface. The interface cannot have any current `AUTO`, `DHCP` or `STATIC` links.
  - **`subnet`** (*integer*, Required): Subnet id linked to interface.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new update interface object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine or interface is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/interfaces/{id}/op-remove_tag: Remove a tag from an interface

  Remove a tag from an interface with the given system_id and interface id.

  **Operation ID:** `InterfaceHandler_remove_tag`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A system_id.
  - **`{id}`** (*integer*, path parameter, Required): An interface id.

  **Request body (multipart/form-data):**

  - **`tag`** (*string*, Optional): The tag to remove.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated interface object.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  If the user does not have the permission to add a tag.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine or interface is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/interfaces/{id}/op-set_default_gateway: Set the default gateway on a machine

  Set the given interface id on the given system_id as the default gateway.
If this interface has more than one subnet with a gateway IP in the same IP address family then specifying the ID of the link on this interface is required.

  **Operation ID:** `InterfaceHandler_set_default_gateway`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A system_id.
  - **`{id}`** (*integer*, path parameter, Required): An interface id.

  **Request body (multipart/form-data):**

  - **`link_id`** (*integer*, Optional): ID of the link on this interface to select the default gateway IP address from.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated interface object.
  
  Content type: `application/json`

  **HTTP 400 BAD REQUEST**
  
  If the interface has no `AUTO` or `STATIC` links.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine or interface is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/interfaces/{id}/op-unlink_subnet: Unlink interface from subnet

  Unlink an interface with the given system_id and interface id from a subnet.

  **Operation ID:** `InterfaceHandler_unlink_subnet`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A system_id.
  - **`{id}`** (*integer*, path parameter, Required): An interface id.

  **Request body (multipart/form-data):**

  - **`id`** (*integer*, Optional): ID of the subnet link on the interface to remove.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated interface object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine or interface is not found.
  
  Content type: `text/plain`

````

## Interfaces

Operations for interfaces resources.

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/interfaces/: List interfaces

  List all interfaces belonging to a machine, device, or rack controller.

  **Operation ID:** `InterfacesHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of interface objects.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/interfaces/op-create_bond: Create a bond inteface

  Create a bond interface on a machine.

  **Operation ID:** `InterfacesHandler_create_bond`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A system_id.

  **Request body (multipart/form-data):**

  - **`accept_ra`** (*boolean*, Optional): Accept router advertisements. (IPv6 only)
  - **`bond_downdelay`** (*integer*, Optional): Specifies the time, in milliseconds, to wait before disabling a slave after a link failure has been detected.
  - **`bond_lacp_rate`** (*string*, Optional): Option specifying the rate at which to ask the link partner to transmit LACPDU packets in 802.3ad mode. Available options are `fast` or `slow`. (Default: `slow`).
  - **`bond_miimon`** (*integer*, Optional): The link monitoring freqeuncy in milliseconds. (Default: 100).
  - **`bond_mode`** (*string*, Optional): The operating mode of the bond. (Default: active-backup). Supported bonding modes: - `balance-rr`: Transmit packets in sequential order from the first available slave through the last. This mode provides load balancing and fault tolerance. - `active-backup`: Only one slave in the bond is active. A different slave becomes active if, and only if, the active slave fails. The bond's MAC address is externally visible on only one port (network adapter) to avoid confusing the switch. - `balance-xor`: Transmit based on the selected transmit hash policy. The default policy is a simple [(source MAC address XOR'd with destination MAC address XOR packet type ID) modulo slave count]. - `broadcast`: Transmits everything on all slave interfaces. This mode provides fault tolerance. - `802.3ad`: IEEE 802.3ad dynamic link aggregation. Creates aggregation groups that share the same speed and duplex settings. Uses all slaves in the active aggregator according to the 802.3ad specification. - `balance-tlb`: Adaptive transmit load balancing: channel bonding that does not require any special switch support. - `balance-alb`: Adaptive load balancing: includes balance-tlb plus receive load balancing (rlb) for IPV4 traffic, and does not require any special switch support. The receive load balancing is achieved by ARP negotiation.
  - **`bond_num_grat_arp`** (*integer*, Optional): The number of peer notifications (IPv4 ARP or IPv6 Neighbour Advertisements) to be issued after a failover. (Default: 1)
  - **`bond_updelay`** (*integer*, Optional): Specifies the time, in milliseconds, to wait before enabling a slave after a link recovery has been detected.
  - **`bond_xmit_hash_policy`** (*string*, Optional): The transmit hash policy to use for slave selection in balance-xor, 802.3ad, and tlb modes. Possible values are: `layer2`, `layer2+3`, `layer3+4`, `encap2+3`, `encap3+4`. (Default: `layer2`)
  - **`mac_address`** (*string*, Optional): MAC address of the interface.
  - **`mtu`** (*integer*, Optional): Maximum transmission unit.
  - **`name`** (*string*, Required): Name of the interface.
  - **`parents`** (*integer*, Required): Parent interface ids that make this bond.
  - **`tags`** (*string*, Optional): Tags for the interface.
  - **`vlan`** (*string*, Optional): VLAN the interface is connected to. If not provided then the interface is considered disconnected.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new bond interface object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/interfaces/op-create_bridge: Create a bridge interface

  Create a bridge interface on a machine.

  **Operation ID:** `InterfacesHandler_create_bridge`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A system_id.

  **Request body (multipart/form-data):**

  - **`accept_ra`** (*boolean*, Optional): Accept router advertisements. (IPv6 only)
  - **`bridge_fd`** (*integer*, Optional): Set bridge forward delay to time seconds. (Default: 15).
  - **`bridge_stp`** (*boolean*, Optional): Turn spanning tree protocol on or off. (Default: False).
  - **`bridge_type`** (*string*, Optional): The type of bridge to create. Possible values are: `standard`, `ovs`.
  - **`mac_address`** (*string*, Optional): MAC address of the interface.
  - **`mtu`** (*integer*, Optional): Maximum transmission unit.
  - **`name`** (*string*, Optional): Name of the interface.
  - **`parent`** (*integer*, Optional): Deprecated, use parents instead. Parent interface id for this bridge interface.
  - **`parents`** (*integer*, Optional): Parent interface ids that make this bridge.
  - **`tags`** (*string*, Optional): Tags for the interface.
  - **`vlan`** (*string*, Optional): VLAN the interface is connected to.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new bridge interface object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/interfaces/op-create_physical: Create a physical interface

  Create a physical interface on a machine and device.

  **Operation ID:** `InterfacesHandler_create_physical`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A system_id.

  **Request body (multipart/form-data):**

  - **`accept_ra`** (*boolean*, Optional): Accept router advertisements. (IPv6 only)
  - **`mac_address`** (*string*, Required): MAC address of the interface.
  - **`mtu`** (*integer*, Optional): Maximum transmission unit.
  - **`name`** (*string*, Optional): Name of the interface.
  - **`tags`** (*string*, Optional): Tags for the interface.
  - **`vlan`** (*string*, Optional): Untagged VLAN the interface is connected to. If not provided then the interface is considered disconnected.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new interface object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/interfaces/op-create_vlan: Create a VLAN interface

  Create a VLAN interface on a machine.

  **Operation ID:** `InterfacesHandler_create_vlan`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A system_id.

  **Request body (multipart/form-data):**

  - **`accept_ra`** (*boolean*, Optional): Accept router advertisements. (IPv6 only)
  - **`mtu`** (*integer*, Optional): Maximum transmission unit.
  - **`parent`** (*integer*, Required): Parent interface id for this VLAN interface.
  - **`tags`** (*string*, Optional): Tags for the interface.
  - **`vlan`** (*string*, Required): Tagged VLAN the interface is connected to.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new VLAN interface object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

## License Key

Operations for license key resources.

````{dropdown} DELETE /MAAS/api/2.0/license-key/{osystem}/{distro_series}: Delete license key

  Delete license key for the given operation system and distro series.

  **Operation ID:** `LicenseKeyHandler_delete`

  **Parameters:**

  - **`{osystem}`** (*string*, path parameter, Required): 
  - **`{distro_series}`** (*string*, path parameter, Required): 
  - **`{osystem}`** (*string*, path parameter, Required): Operating system that the key belongs to.
  - **`{distro_series}`** (*string*, path parameter, Required): OS release that the key belongs to.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested operating system and distro series combination is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/license-key/{osystem}/{distro_series}: Read license key

  Read a license key for the given operating sytem and distro series.

  **Operation ID:** `LicenseKeyHandler_read`

  **Parameters:**

  - **`{osystem}`** (*string*, path parameter, Required): 
  - **`{distro_series}`** (*string*, path parameter, Required): 
  - **`{osystem}`** (*string*, path parameter, Required): Operating system that the key belongs to.
  - **`{distro_series}`** (*string*, path parameter, Required): OS release that the key belongs to.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested license key.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested operating system and distro series combination is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/license-key/{osystem}/{distro_series}: Update license key

  Update a license key for the given operating system and distro series.

  **Operation ID:** `LicenseKeyHandler_update`

  **Parameters:**

  - **`{osystem}`** (*string*, path parameter, Required): 
  - **`{distro_series}`** (*string*, path parameter, Required): 
  - **`{osystem}`** (*string*, path parameter, Required): Operating system that the key belongs to.
  - **`{distro_series}`** (*string*, path parameter, Required): OS release that the key belongs to.

  **Request body (multipart/form-data):**

  - **`license_key`** (*string*, Optional): License key for osystem/distro_series combo.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated license key.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested operating system and distro series combination is not found.
  
  Content type: `text/plain`

````

## License Keys

Operations for license keys resources.

````{dropdown} GET /MAAS/api/2.0/license-keys/: List license keys

  List all available license keys.

  **Operation ID:** `LicenseKeysHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of available license keys.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/license-keys/: Define a license key

  Define a license key.

  **Operation ID:** `LicenseKeysHandler_create`

  **Request body (multipart/form-data):**

  - **`distro_series`** (*string*, Required): OS release that the key belongs to.
  - **`license_key`** (*string*, Required): License key for osystem/distro_series combo.
  - **`osystem`** (*string*, Required): Operating system that the key belongs to.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new license key.
  
  Content type: `application/json`

````

## Logged-in user

Operations for logged-in user resources.

````{dropdown} POST /MAAS/api/2.0/account/op-create_authorisation_token: Create an authorisation token

  Create an authorisation OAuth token and OAuth consumer.

  **Operation ID:** `AccountHandler_create_authorisation_token`

  **Request body (multipart/form-data):**

  - **`name`** (*string*, Optional): Optional name of the token that will be generated.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing: `token_key`, `token_secret`, `consumer_key`, and `name`.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/account/op-delete_authorisation_token: Delete an authorisation token

  Delete an authorisation OAuth token and the related OAuth consumer.

  **Operation ID:** `AccountHandler_delete_authorisation_token`

  **Request body (multipart/form-data):**

  - **`token_key`** (*string*, Required): The key of the token to be deleted.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

````

````{dropdown} GET /MAAS/api/2.0/account/op-list_authorisation_tokens: List authorisation tokens

  List authorisation tokens available to the currently logged-in user.

  **Operation ID:** `AccountHandler_list_authorisation_tokens`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of token objects.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/account/op-update_token_name: Modify authorisation token

  Modify the consumer name of an authorisation OAuth token.

  **Operation ID:** `AccountHandler_update_token_name`

  **Request body (multipart/form-data):**

  - **`name`** (*string*, Required): New name of the token.
  - **`token`** (*string*, Required): Can be the whole token or only the token key.

  **Responses:**

  **HTTP 200 OK**
  
  Accepted
  
  Content type: `text/plain`

````

## MAAS server

Operations for maas server resources.

````{dropdown} GET /MAAS/api/2.0/maas/op-get_config: Get a configuration value

  Get a configuration value.

  **Operation ID:** `MaasHandler_get_config`

  **Parameters:**

  - **`name`** (*string*, Required): The name of the configuration item to be retrieved. Available configuration items:
* `active_discovery_interval` Active subnet mapping interval. When enabled, each rack will scan subnets enabled for active mapping. This helps ensure discovery information is accurate and complete.
* `allow_only_trusted_transfers` Allow only trusted zone transfers. A boolean value to allow only zone transfers from trusted sources. If set to false, zone transfers from all sources will be allowed.
* `auto_vlan_creation` Automatically create VLANs and Fabrics for interfaces. Enables the creation of a default VLAN and Fabric for discovered network interfaces when MAAS cannot connect it to an existing one. When disabled, the interface is left disconnected in these cases.
* `boot_images_auto_import` Automatically import/refresh the boot images every 60.0 minutes.
* `boot_images_no_proxy` Set no_proxy with the image repository address when MAAS is behind (or set with) a proxy. By default, when MAAS is behind (and set with) a proxy, it is used to download images from the image repository. In some situations (e.g. when using a local image repository) it doesn't make sense for MAAS to use the proxy to download images because it can access them directly. Setting this option allows MAAS to access the (local) image repository directly by setting the no_proxy variable for the MAAS env with the address of the image repository.
* `commissioning_distro_series` Default Ubuntu release used for commissioning.
* `completed_intro` Marks if the initial intro has been completed.
* `curtin_verbose` Run the fast-path installer with higher verbosity. This provides more detail in the installation logs.
* `default_boot_interface_link_type` Default boot interface IP Mode. IP Mode that is applied to the boot interface on a node when it is commissioned. Available choices are:
  + `auto` (Auto IP).
  + `dhcp` (DHCP).
  + `link_up` (Link up).
  + `static` (Static IP).
* `default_distro_series` Default OS release used for deployment.
* `default_dns_ttl` Default Time-To-Live for the DNS. If no TTL value is specified at a more specific point this is how long DNS responses are valid, in seconds.
* `default_min_hwe_kernel` Default Minimum Kernel Version. The default minimum kernel version used on all new and commissioned nodes.
* `default_osystem` Default operating system used for deployment.
* `default_storage_layout` Default storage layout. Storage layout that is applied to a node when it is commissioned. Available choices are:
  + `bcache` (Bcache layout).
  + `blank` (No storage (blank) layout).
  + `custom` (Custom layout (from commissioning storage config).
  + `flat` (Flat layout).
  + `lvm` (LVM layout).
  + `vmfs6` (VMFS6 layout).
  + `vmfs7` (VMFS7 layout).
* `disk_erase_with_quick_erase` Use quick erase by default when erasing disks. This is not a secure erase; it wipes only the beginning and end of each disk.
* `disk_erase_with_secure_erase` Use secure erase by default when erasing disks. Will only be used on devices that support secure erase. Other devices will fall back to full wipe or quick erase depending on the selected options.
* `dns_trusted_acl` List of external networks (not previously known), that will be allowed to use MAAS for DNS resolution. MAAS keeps a list of networks that are allowed to use MAAS for DNS resolution. This option allows to add extra networks (not previously known) to the trusted ACL where this list of networks is kept. It also supports specifying IPs or ACL names.
* `dnssec_validation` Enable DNSSEC validation of upstream zones. Only used when MAAS is running its own DNS server. This value is used as the value of 'dnssec_validation' in the DNS server config.
* `enable_analytics` Enable Google Analytics in MAAS UI to shape improvements in user experience.
* `enable_disk_erasing_on_release` Erase nodes' disks prior to releasing. Forces users to always erase disks when releasing.
* `enable_http_proxy` Enable the use of an APT or YUM and HTTP/HTTPS proxy. Provision nodes to use the built-in HTTP proxy (or user specified proxy) for APT or YUM. MAAS also uses the proxy for downloading boot images.
* `enable_kernel_crash_dump` Enable the kernel crash dump feature in deployed machines. Enable the collection of kernel crash dump when a machine is deployed.
* `enable_third_party_drivers` Enable the installation of proprietary drivers (i.e. HPVSA).
* `enlist_commissioning` Whether to run commissioning during enlistment. Enables running all built-in commissioning scripts during enlistment.
* `force_v1_network_yaml` Always use the legacy v1 YAML (rather than Netplan format, also known as v2 YAML) when composing the network configuration for a machine.
* `hardware_sync_interval` Hardware Sync Interval. The interval to send hardware info to MAAS fromhardware sync enabled machines, in systemd time span syntax.
* `http_proxy` Proxy for APT or YUM and HTTP/HTTPS. This will be passed onto provisioned nodes to use as a proxy for APT or YUM traffic. MAAS also uses the proxy for downloading boot images. If no URL is provided, the built-in MAAS proxy will be used.
* `kernel_opts` Boot parameters to pass to the kernel by default.
* `maas_auto_ipmi_cipher_suite_id` MAAS IPMI Default Cipher Suite ID. The default IPMI cipher suite ID to use when connecting to the BMC via ipmitools Available choices are:
  + ` ` (freeipmi-tools default).
  + `12` (12 - HMAC-MD5:MD5-128:AES-CBC-128).
  + `17` (17 - HMAC-SHA256:HMAC_SHA256_128:AES-CBC-128).
  + `3` (3 - HMAC-SHA1:HMAC-SHA1-96:AES-CBC-128).
  + `8` (8 - HMAC-MD5:HMAC-MD5-128:AES-CBC-128).
* `maas_auto_ipmi_k_g_bmc_key` The IPMI K_g key to set during BMC configuration. This IPMI K_g BMC key is used to encrypt all IPMI traffic to a BMC. Once set, all clients will REQUIRE this key upon being commissioned. Any current machines that were previously commissioned will not require this key until they are recommissioned.
* `maas_auto_ipmi_user` MAAS IPMI user. The name of the IPMI user that MAAS automatically creates during enlistment/commissioning.
* `maas_auto_ipmi_user_privilege_level` MAAS IPMI privilege level. The default IPMI privilege level to use when creating the MAAS user and talking IPMI BMCs Available choices are:
  + `ADMIN` (Administrator).
  + `OPERATOR` (Operator).
  + `USER` (User).
* `maas_auto_ipmi_workaround_flags` IPMI Workaround Flags. The default workaround flag (-W options) to use for ipmipower commands Available choices are:
  + ` ` (None).
  + `authcap` (Authcap).
  + `endianseq` (Endianseq).
  + `forcepermsg` (Forcepermsg).
  + `idzero` (Idzero).
  + `integritycheckvalue` (Integritycheckvalue).
  + `intel20` (Intel20).
  + `ipmiping` (Ipmiping).
  + `nochecksumcheck` (Nochecksumcheck).
  + `opensesspriv` (Opensesspriv).
  + `sun20` (Sun20).
  + `supermicro20` (Supermicro20).
  + `unexpectedauth` (Unexpectedauth).
* `maas_internal_domain` Domain name used by MAAS for internal mapping of MAAS provided services. This domain should not collide with an upstream domain provided by the set upstream DNS.
* `maas_name` MAAS name.
* `maas_proxy_port` Port to bind the MAAS built-in proxy (default: 8000). Defines the port used to bind the built-in proxy. The default port is 8000.
* `maas_syslog_port` Port to bind the MAAS built-in syslog (default: 5247). Defines the port used to bind the built-in syslog. The default port is 5247.
* `max_node_commissioning_results` The maximum number of commissioning results runs which are stored.
* `max_node_installation_results` The maximum number of installation result runs which are stored.
* `max_node_release_results` The maximum number of release result runs which are stored.
* `max_node_testing_results` The maximum number of testing results runs which are stored.
* `network_discovery`  When enabled, MAAS will use passive techniques (such as listening to ARP requests and mDNS advertisements) to observe networks attached to rack controllers. Active subnet mapping will also be available to be enabled on the configured subnets.
* `node_timeout` Time, in minutes, until the node times out during commissioning, testing, deploying, or entering rescue mode. Commissioning, testing, deploying, and entering rescue mode all set a timeout when beginning. If MAAS does not hear from the node within the specified number of minutes the node is powered off and set into a failed status.
* `ntp_external_only` Use external NTP servers only. Configure all region controller hosts, rack controller hosts, and subsequently deployed machines to refer directly to the configured external NTP servers. Otherwise only region controller hosts will be configured to use those external NTP servers, rack contoller hosts will in turn refer to the regions' NTP servers, and deployed machines will refer to the racks' NTP servers.
* `ntp_servers` Addresses of NTP servers. NTP servers, specified as IP addresses or hostnames delimited by commas and/or spaces, to be used as time references for MAAS itself, the machines MAAS deploys, and devices that make use of MAAS's DHCP services.
* `prefer_v4_proxy` Sets IPv4 DNS resolution before IPv6. If prefer_v4_proxy is set, the proxy will be set to prefer IPv4 DNS resolution before it attempts to perform IPv6 DNS resolution.
* `prometheus_enabled` Enable Prometheus exporter. Whether to enable Prometheus exporter functions, including Cluster metrics endpoint and Push gateway (if configured).
* `prometheus_push_gateway` Address or hostname of the Prometheus push gateway. Defines the address or hostname of the Prometheus push gateway where MAAS will send data to.
* `prometheus_push_interval` Interval of how often to send data to Prometheus (default: to 60 minutes). The internal of how often MAAS will send stats to Prometheus in minutes.
* `promtail_enabled` Enable streaming logs to Promtail. Whether to stream logs to Promtail.
* `promtail_port` TCP port of the Promtail Push API. Defines the TCP port of the Promtail push API where MAAS will stream logs to.
* `refresh_token_duration` Refresh token duration (seconds). Configure duration of refresh token (seconds). Minimum 10 minutes, maximum 60 days (5184000s).
* `release_notifications` Enable or disable notifications for new MAAS releases.
* `remote_syslog` Remote syslog server to forward machine logs. A remote syslog server that MAAS will set on enlisting, commissioning, testing, and deploying machines to send all log messages. Clearing this value will restore the default behaviour of forwarding syslog to MAAS.
* `session_length` Session timeout (seconds). Configure timeout of session (seconds). Minimum 10s, maximum 2 weeks (1209600s).
* `subnet_ip_exhaustion_threshold_count` If the number of free IP addresses on a subnet becomes less than or equal to this threshold, an IP exhaustion warning will appear for that subnet.
* `theme` MAAS theme.
* `tls_cert_expiration_notification_enabled` Notify when the certificate is due to expire. Enable/Disable notification about certificate expiration.
* `tls_cert_expiration_notification_interval` Certificate expiration reminder (days). Configure notification when certificate is due to expire in (days).
* `upstream_dns` Upstream DNS used to resolve domains not managed by this MAAS (space-separated IP addresses). Only used when MAAS is running its own DNS server. This value is used as the value of 'forwarders' in the DNS server config.
* `use_peer_proxy` Use the built-in proxy with an external proxy as a peer. If enable_http_proxy is set, the built-in proxy will be configured to use http_proxy as a peer proxy. The deployed machines will be configured to use the built-in proxy.
* `use_rack_proxy` Use DNS and HTTP metadata proxy on the rack controllers when a machine is booted. All DNS and HTTP metadata traffic will flow through the rack controller that a machine is booting from. This isolated region controllers from machines.
* `vcenter_datacenter` VMware vCenter datacenter. VMware vCenter datacenter which is passed to a deployed VMware ESXi host.
* `vcenter_password` VMware vCenter password. VMware vCenter server password which is passed to a deployed VMware ESXi host.
* `vcenter_server` VMware vCenter server FQDN or IP address. VMware vCenter server FQDN or IP address which is passed to a deployed VMware ESXi host.
* `vcenter_username` VMware vCenter username. VMware vCenter server username which is passed to a deployed VMware ESXi host.
* `windows_kms_host` Windows KMS activation host. FQDN or IP address of the host that provides the KMS Windows activation service. (Only needed for Windows deployments using KMS activation.).

  **Responses:**

  **HTTP 200 OK**
  
  A plain-text string containing the requested value, e.g. `default_distro_series`.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/maas/op-set_config: Set a configuration value

  Set a configuration value.

  **Operation ID:** `MaasHandler_set_config`

  **Request body (multipart/form-data):**

  - **`name`** (*string*, Required): The name of the configuration item to be set. Available configuration items:
* `active_discovery_interval` Active subnet mapping interval. When enabled, each rack will scan subnets enabled for active mapping. This helps ensure discovery information is accurate and complete.
* `allow_only_trusted_transfers` Allow only trusted zone transfers. A boolean value to allow only zone transfers from trusted sources. If set to false, zone transfers from all sources will be allowed.
* `auto_vlan_creation` Automatically create VLANs and Fabrics for interfaces. Enables the creation of a default VLAN and Fabric for discovered network interfaces when MAAS cannot connect it to an existing one. When disabled, the interface is left disconnected in these cases.
* `boot_images_auto_import` Automatically import/refresh the boot images every 60.0 minutes.
* `boot_images_no_proxy` Set no_proxy with the image repository address when MAAS is behind (or set with) a proxy. By default, when MAAS is behind (and set with) a proxy, it is used to download images from the image repository. In some situations (e.g. when using a local image repository) it doesn't make sense for MAAS to use the proxy to download images because it can access them directly. Setting this option allows MAAS to access the (local) image repository directly by setting the no_proxy variable for the MAAS env with the address of the image repository.
* `commissioning_distro_series` Default Ubuntu release used for commissioning.
* `completed_intro` Marks if the initial intro has been completed.
* `curtin_verbose` Run the fast-path installer with higher verbosity. This provides more detail in the installation logs.
* `default_boot_interface_link_type` Default boot interface IP Mode. IP Mode that is applied to the boot interface on a node when it is commissioned. Available choices are:
  + `auto` (Auto IP).
  + `dhcp` (DHCP).
  + `link_up` (Link up).
  + `static` (Static IP).
* `default_distro_series` Default OS release used for deployment.
* `default_dns_ttl` Default Time-To-Live for the DNS. If no TTL value is specified at a more specific point this is how long DNS responses are valid, in seconds.
* `default_min_hwe_kernel` Default Minimum Kernel Version. The default minimum kernel version used on all new and commissioned nodes.
* `default_osystem` Default operating system used for deployment.
* `default_storage_layout` Default storage layout. Storage layout that is applied to a node when it is commissioned. Available choices are:
  + `bcache` (Bcache layout).
  + `blank` (No storage (blank) layout).
  + `custom` (Custom layout (from commissioning storage config).
  + `flat` (Flat layout).
  + `lvm` (LVM layout).
  + `vmfs6` (VMFS6 layout).
  + `vmfs7` (VMFS7 layout).
* `disk_erase_with_quick_erase` Use quick erase by default when erasing disks. This is not a secure erase; it wipes only the beginning and end of each disk.
* `disk_erase_with_secure_erase` Use secure erase by default when erasing disks. Will only be used on devices that support secure erase. Other devices will fall back to full wipe or quick erase depending on the selected options.
* `dns_trusted_acl` List of external networks (not previously known), that will be allowed to use MAAS for DNS resolution. MAAS keeps a list of networks that are allowed to use MAAS for DNS resolution. This option allows to add extra networks (not previously known) to the trusted ACL where this list of networks is kept. It also supports specifying IPs or ACL names.
* `dnssec_validation` Enable DNSSEC validation of upstream zones. Only used when MAAS is running its own DNS server. This value is used as the value of 'dnssec_validation' in the DNS server config.
* `enable_analytics` Enable Google Analytics in MAAS UI to shape improvements in user experience.
* `enable_disk_erasing_on_release` Erase nodes' disks prior to releasing. Forces users to always erase disks when releasing.
* `enable_http_proxy` Enable the use of an APT or YUM and HTTP/HTTPS proxy. Provision nodes to use the built-in HTTP proxy (or user specified proxy) for APT or YUM. MAAS also uses the proxy for downloading boot images.
* `enable_kernel_crash_dump` Enable the kernel crash dump feature in deployed machines. Enable the collection of kernel crash dump when a machine is deployed.
* `enable_third_party_drivers` Enable the installation of proprietary drivers (i.e. HPVSA).
* `enlist_commissioning` Whether to run commissioning during enlistment. Enables running all built-in commissioning scripts during enlistment.
* `force_v1_network_yaml` Always use the legacy v1 YAML (rather than Netplan format, also known as v2 YAML) when composing the network configuration for a machine.
* `hardware_sync_interval` Hardware Sync Interval. The interval to send hardware info to MAAS fromhardware sync enabled machines, in systemd time span syntax.
* `http_proxy` Proxy for APT or YUM and HTTP/HTTPS. This will be passed onto provisioned nodes to use as a proxy for APT or YUM traffic. MAAS also uses the proxy for downloading boot images. If no URL is provided, the built-in MAAS proxy will be used.
* `kernel_opts` Boot parameters to pass to the kernel by default.
* `maas_auto_ipmi_cipher_suite_id` MAAS IPMI Default Cipher Suite ID. The default IPMI cipher suite ID to use when connecting to the BMC via ipmitools Available choices are:
  + ` ` (freeipmi-tools default).
  + `12` (12 - HMAC-MD5:MD5-128:AES-CBC-128).
  + `17` (17 - HMAC-SHA256:HMAC_SHA256_128:AES-CBC-128).
  + `3` (3 - HMAC-SHA1:HMAC-SHA1-96:AES-CBC-128).
  + `8` (8 - HMAC-MD5:HMAC-MD5-128:AES-CBC-128).
* `maas_auto_ipmi_k_g_bmc_key` The IPMI K_g key to set during BMC configuration. This IPMI K_g BMC key is used to encrypt all IPMI traffic to a BMC. Once set, all clients will REQUIRE this key upon being commissioned. Any current machines that were previously commissioned will not require this key until they are recommissioned.
* `maas_auto_ipmi_user` MAAS IPMI user. The name of the IPMI user that MAAS automatically creates during enlistment/commissioning.
* `maas_auto_ipmi_user_privilege_level` MAAS IPMI privilege level. The default IPMI privilege level to use when creating the MAAS user and talking IPMI BMCs Available choices are:
  + `ADMIN` (Administrator).
  + `OPERATOR` (Operator).
  + `USER` (User).
* `maas_auto_ipmi_workaround_flags` IPMI Workaround Flags. The default workaround flag (-W options) to use for ipmipower commands Available choices are:
  + ` ` (None).
  + `authcap` (Authcap).
  + `endianseq` (Endianseq).
  + `forcepermsg` (Forcepermsg).
  + `idzero` (Idzero).
  + `integritycheckvalue` (Integritycheckvalue).
  + `intel20` (Intel20).
  + `ipmiping` (Ipmiping).
  + `nochecksumcheck` (Nochecksumcheck).
  + `opensesspriv` (Opensesspriv).
  + `sun20` (Sun20).
  + `supermicro20` (Supermicro20).
  + `unexpectedauth` (Unexpectedauth).
* `maas_internal_domain` Domain name used by MAAS for internal mapping of MAAS provided services. This domain should not collide with an upstream domain provided by the set upstream DNS.
* `maas_name` MAAS name.
* `maas_proxy_port` Port to bind the MAAS built-in proxy (default: 8000). Defines the port used to bind the built-in proxy. The default port is 8000.
* `maas_syslog_port` Port to bind the MAAS built-in syslog (default: 5247). Defines the port used to bind the built-in syslog. The default port is 5247.
* `max_node_commissioning_results` The maximum number of commissioning results runs which are stored.
* `max_node_installation_results` The maximum number of installation result runs which are stored.
* `max_node_release_results` The maximum number of release result runs which are stored.
* `max_node_testing_results` The maximum number of testing results runs which are stored.
* `network_discovery`  When enabled, MAAS will use passive techniques (such as listening to ARP requests and mDNS advertisements) to observe networks attached to rack controllers. Active subnet mapping will also be available to be enabled on the configured subnets.
* `node_timeout` Time, in minutes, until the node times out during commissioning, testing, deploying, or entering rescue mode. Commissioning, testing, deploying, and entering rescue mode all set a timeout when beginning. If MAAS does not hear from the node within the specified number of minutes the node is powered off and set into a failed status.
* `ntp_external_only` Use external NTP servers only. Configure all region controller hosts, rack controller hosts, and subsequently deployed machines to refer directly to the configured external NTP servers. Otherwise only region controller hosts will be configured to use those external NTP servers, rack contoller hosts will in turn refer to the regions' NTP servers, and deployed machines will refer to the racks' NTP servers.
* `ntp_servers` Addresses of NTP servers. NTP servers, specified as IP addresses or hostnames delimited by commas and/or spaces, to be used as time references for MAAS itself, the machines MAAS deploys, and devices that make use of MAAS's DHCP services.
* `prefer_v4_proxy` Sets IPv4 DNS resolution before IPv6. If prefer_v4_proxy is set, the proxy will be set to prefer IPv4 DNS resolution before it attempts to perform IPv6 DNS resolution.
* `prometheus_enabled` Enable Prometheus exporter. Whether to enable Prometheus exporter functions, including Cluster metrics endpoint and Push gateway (if configured).
* `prometheus_push_gateway` Address or hostname of the Prometheus push gateway. Defines the address or hostname of the Prometheus push gateway where MAAS will send data to.
* `prometheus_push_interval` Interval of how often to send data to Prometheus (default: to 60 minutes). The internal of how often MAAS will send stats to Prometheus in minutes.
* `promtail_enabled` Enable streaming logs to Promtail. Whether to stream logs to Promtail.
* `promtail_port` TCP port of the Promtail Push API. Defines the TCP port of the Promtail push API where MAAS will stream logs to.
* `refresh_token_duration` Refresh token duration (seconds). Configure duration of refresh token (seconds). Minimum 10 minutes, maximum 60 days (5184000s).
* `release_notifications` Enable or disable notifications for new MAAS releases.
* `remote_syslog` Remote syslog server to forward machine logs. A remote syslog server that MAAS will set on enlisting, commissioning, testing, and deploying machines to send all log messages. Clearing this value will restore the default behaviour of forwarding syslog to MAAS.
* `session_length` Session timeout (seconds). Configure timeout of session (seconds). Minimum 10s, maximum 2 weeks (1209600s).
* `subnet_ip_exhaustion_threshold_count` If the number of free IP addresses on a subnet becomes less than or equal to this threshold, an IP exhaustion warning will appear for that subnet.
* `theme` MAAS theme.
* `tls_cert_expiration_notification_enabled` Notify when the certificate is due to expire. Enable/Disable notification about certificate expiration.
* `tls_cert_expiration_notification_interval` Certificate expiration reminder (days). Configure notification when certificate is due to expire in (days).
* `upstream_dns` Upstream DNS used to resolve domains not managed by this MAAS (space-separated IP addresses). Only used when MAAS is running its own DNS server. This value is used as the value of 'forwarders' in the DNS server config.
* `use_peer_proxy` Use the built-in proxy with an external proxy as a peer. If enable_http_proxy is set, the built-in proxy will be configured to use http_proxy as a peer proxy. The deployed machines will be configured to use the built-in proxy.
* `use_rack_proxy` Use DNS and HTTP metadata proxy on the rack controllers when a machine is booted. All DNS and HTTP metadata traffic will flow through the rack controller that a machine is booting from. This isolated region controllers from machines.
* `vcenter_datacenter` VMware vCenter datacenter. VMware vCenter datacenter which is passed to a deployed VMware ESXi host.
* `vcenter_password` VMware vCenter password. VMware vCenter server password which is passed to a deployed VMware ESXi host.
* `vcenter_server` VMware vCenter server FQDN or IP address. VMware vCenter server FQDN or IP address which is passed to a deployed VMware ESXi host.
* `vcenter_username` VMware vCenter username. VMware vCenter server username which is passed to a deployed VMware ESXi host.
* `windows_kms_host` Windows KMS activation host. FQDN or IP address of the host that provides the KMS Windows activation service. (Only needed for Windows deployments using KMS activation.).
  - **`value`** (*string*, Optional): The value of the configuration item to be set.

  **Responses:**

  **HTTP 200 OK**
  
  A plain-text string
  
  Content type: `text/plain`

````

## MAAS version

Operations for maas version resources.

````{dropdown} GET /MAAS/api/2.0/version/: MAAS version information

  Read version and capabilities of this MAAS instance.

  **Operation ID:** `VersionHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing MAAS version and capabilities information.
  
  Content type: `application/json`

````

## Machine

Operations for machine resources.

````{dropdown} DELETE /MAAS/api/2.0/machines/{system_id}/: Delete a machine

  Deletes a machine with the given system_id.
Note: A machine cannot be deleted if it hosts pod virtual machines.
Use `force` to override this behavior. Forcing deletion will also remove hosted pods. E.g. `/machines/abc123/?force=1`.

  **Operation ID:** `MachineHandler_delete`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machines's system_id.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 400 BAD REQUEST**
  
  The machine cannot be deleted.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to delete this machine.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested static-route is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/machines/{system_id}/: Read a node

  Reads a node with the given system_id.

  **Operation ID:** `MachineHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A node's system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the requested node.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/machines/{system_id}/: Update a machine

  Updates a machine with the given system_id.

  **Operation ID:** `MachineHandler_update`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machines's system_id.

  **Request body (multipart/form-data):**

  - **`architecture`** (*string*, Optional): The new architecture for this machine.
  - **`cpu_count`** (*integer*, Optional): The amount of CPU cores the machine has.
  - **`description`** (*string*, Optional): The new description for this machine.
  - **`disable_ipv4`** (*boolean*, Optional): Deprecated. If specified, must be false.
  - **`domain`** (*string*, Optional): The domain for this machine. If not given the default domain is used.
  - **`hostname`** (*string*, Optional): The new hostname for this machine.
  - **`memory`** (*string*, Optional): How much memory the machine has. Field accept K, M, G and T suffixes for values expressed respectively in kilobytes, megabytes, gigabytes and terabytes.
  - **`min_hwe_kernel`** (*string*, Optional): A string containing the minimum kernel version allowed to be ran on this machine.
  - **`pool`** (*string*, Optional): The resource pool to which the machine should belong. All machines belong to the 'default' resource pool if they do not belong to any other resource pool.
  - **`power_parameters_skip_check`** (*boolean*, Optional): Whether or not the new power parameters for this machine should be checked against the expected power parameters for the machine's power type ('true' or 'false'). The default is 'false'.
  - **`power_parameters_{param1}`** (*string*, Optional): The new value for the 'param1' power parameter. Note that this is dynamic as the available parameters depend on the selected value of the Machine's power_type. Available to admin users. See the `Power types`_ section for a list of the available power parameters for each power type.
  - **`power_type`** (*string*, Optional): The new power type for this machine. If you use the default value, power_parameters will be set to the empty string. Available to admin users. See the `Power types`_ section for a list of the available power types.
  - **`swap_size`** (*string*, Optional): Specifies the size of the swap file, in bytes. Field accept K, M, G and T suffixes for values expressed respectively in kilobytes, megabytes, gigabytes and terabytes.
  - **`zone`** (*string*, Optional): Name of a valid physical zone in which to place this machine.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the updated machine.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to update this machine.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-abort: Abort a node operation

  Abort a node's current operation.

  **Operation ID:** `MachineHandler_abort`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 

  **Request body (multipart/form-data):**

  - **`comment`** (*string*, Optional): Comment for the event log.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The user is not authorized to abort the current operation.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-clear_default_gateways: Clear set default gateways

  Clear any set default gateways on a machine with the given system_id.
This will clear both IPv4 and IPv6 gateways on the machine. This will transition the logic of identifing the best gateway to MAAS. This logic is determined based the following criteria:
1. Managed subnets over unmanaged subnets.
2. Bond interfaces over physical interfaces.
3. Machine's boot interface over all other interfaces except bonds.
4. Physical interfaces over VLAN interfaces.
5. Sticky IP links over user reserved IP links.
6. User reserved IP links over auto IP links.
If the default gateways need to be specific for this machine you can set which interface and subnet's gateway to use when this machine is deployed with the `interfaces set-default-gateway` API.

  **Operation ID:** `MachineHandler_clear_default_gateways`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machines's system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the machine.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to clear default gateways on this machine.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-commission: Commission a machine

  Begin commissioning process for a machine.
A machine in the 'ready', 'declared' or 'failed test' state may initiate a commissioning cycle where it is checked out and tested in preparation for transitioning to the 'ready' state. If it is already in the 'ready' state this is considered a re-commissioning process which is useful if commissioning tests were changed after it previously commissioned.

  **Operation ID:** `MachineHandler_commission`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machines's system_id.

  **Request body (multipart/form-data):**

  - **`commissioning_scripts`** (*string*, Optional): A comma seperated list of commissioning script names and tags to be run. By default all custom commissioning scripts are run. Built-in commissioning scripts always run. Selecting 'update_firmware' or 'configure_hba' will run firmware updates or configure HBA's on matching machines.
  - **`enable_ssh`** (*integer*, Optional): Whether to enable SSH for the commissioning environment using the user's SSH key(s). '1' = True, '0' = False.
  - **`parameters`** (*string*, Optional): Scripts selected to run may define their own parameters. These parameters may be passed using the parameter name. Optionally a parameter may have the script name prepended to have that parameter only apply to that specific script.
  - **`skip_bmc_config`** (*integer*, Optional): Whether to skip re-configuration of the BMC for IPMI based machines. '1' = True, '0' = False.
  - **`skip_networking`** (*integer*, Optional): Whether to skip re-configuring the networking on the machine after the commissioning has completed. '1' = True, '0' = False.
  - **`skip_storage`** (*integer*, Optional): Whether to skip re-configuring the storage on the machine after the commissioning has completed. '1' = True, '0' = False.
  - **`testing_scripts`** (*string*, Optional): A comma seperated list of testing script names and tags to be run. By default all tests tagged 'commissioning' will be run. Set to 'none' to disable running tests.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the commissioning machine.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-deploy: Deploy a machine

  Deploys an operating system to a machine with the given system_id.

  **Operation ID:** `MachineHandler_deploy`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machines's system_id.

  **Request body (multipart/form-data):**

  - **`agent_name`** (*string*, Optional): An optional agent name to attach to the acquired machine.
  - **`bridge_all`** (*boolean*, Optional): Optionally create a bridge interface for every configured interface on the machine. The created bridges will be removed once the machine is released. (Default: false)
  - **`bridge_fd`** (*integer*, Optional): Optionally adjust the forward delay to time seconds. (Default: 15)
  - **`bridge_stp`** (*boolean*, Optional): Optionally turn spanning tree protocol on or off for the bridges created on every configured interface. (Default: false)
  - **`bridge_type`** (*string*, Optional): Optionally create the bridges with this type. Possible values are: `standard`, `ovs`.
  - **`comment`** (*string*, Optional): Optional comment for the event log.
  - **`distro_series`** (*string*, Optional): If present, this parameter specifies the OS release the machine will use. For example valid values to deploy Jammy Jellyfish are `ubuntu/jammy`, `jammy` and `ubuntu/22.04`, `22.04`.
  - **`enable_hw_sync`** (*boolean*, Optional): If true, machine will be deployed with a small agent periodically pushing hardware data to detect any change in devices.
  - **`enable_kernel_crash_dump`** (*boolean*, Optional): If true, machine will be deployed with the kernel crash dump feature enabled and configured automatically.
  - **`ephemeral_deploy`** (*boolean*, Optional): If true, machine will be deployed ephemerally even if it has disks.
  - **`hwe_kernel`** (*string*, Optional): If present, this parameter specified the kernel to be used on the machine
  - **`install_kvm`** (*boolean*, Optional): If true, KVM will be installed on this machine and added to MAAS.
  - **`install_rackd`** (*boolean*, Optional): If true, the rack controller will be installed on this machine.
  - **`register_vmhost`** (*boolean*, Optional): If true, the machine will be registered as a LXD VM host in MAAS.
  - **`user_data`** (*string*, Optional): If present, this blob of base64-encoded user-data to be made available to the machines through the metadata service.
  - **`vcenter_registration`** (*boolean*, Optional): If false, do not send globally defined VMware vCenter credentials to the machine.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the deployed machine.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to deploy this machine.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

  **HTTP 503 SERVICE UNAVAILABLE**
  
  MAAS attempted to allocate an IP address, and there were no IP addresses available on the relevant cluster interface.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/machines/{system_id}/op-details: Get system details

  Returns system details - for example, LLDP and `lshw` XML dumps.
Returns a `{detail_type: xml, .}` map, where `detail_type` is something like "lldp" or "lshw".
Note that this is returned as BSON and not JSON. This is for efficiency, but mainly because JSON can't do binary content without applying additional encoding like base-64. The example output below is represented in ASCII using `bsondump example.bson` and is for demonstrative purposes.

  **Operation ID:** `MachineHandler_details`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The node's system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A BSON object represented here in ASCII using `bsondump example.bson`.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to see the node details.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-exit_rescue_mode: Exit rescue mode

  Exits the rescue mode process on a machine with the given system_id.
A machine in the 'rescue mode' state may exit the rescue mode process.

  **Operation ID:** `MachineHandler_exit_rescue_mode`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machines's system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the machine information.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to exit rescue mode on the machine.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/machines/{system_id}/op-get_curtin_config: Get curtin configuration

  Return the rendered curtin configuration for the machine.

  **Operation ID:** `MachineHandler_get_curtin_config`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machines's system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the curtin configuration.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to see curtin configuration on this machine.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/machines/{system_id}/op-get_token: Get a machine token

  Manage an individual machine.
A machine is identified by its system_id.

  **Operation ID:** `MachineHandler_get_token`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machines' system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the machine token.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-lock: Lock a machine

  Mark a machine with the given system_id as 'Locked' to prevent changes.

  **Operation ID:** `MachineHandler_lock`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machines's system_id.

  **Request body (multipart/form-data):**

  - **`comment`** (*string*, Optional): Optional comment for the event log.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the machine information.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to lock the machine.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-mark_broken: Mark a machine as Broken

  Mark a machine with the given system_id as 'Broken'.
If the node is allocated, release it first.

  **Operation ID:** `MachineHandler_mark_broken`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machines's system_id.

  **Request body (multipart/form-data):**

  - **`comment`** (*string*, Optional): Optional comment for the event log. Will be displayed on the node as an error description until marked fixed.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the machine information.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to the machine as Broken.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-mark_fixed: Mark a machine as Fixed

  Mark a machine with the given system_id as 'Fixed'.

  **Operation ID:** `MachineHandler_mark_fixed`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machines's system_id.

  **Request body (multipart/form-data):**

  - **`comment`** (*string*, Optional): Optional comment for the event log.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the machine information.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to the machine as Fixed.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-mount_special: Mount a special-purpose filesystem

  Mount a special-purpose filesystem, like tmpfs on a machine with the given system_id.

  **Operation ID:** `MachineHandler_mount_special`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machines's system_id.

  **Request body (multipart/form-data):**

  - **`fstype`** (*string*, Required): The filesystem type. This must be a filesystem that does not require a block special device.
  - **`mount_option`** (*string*, Optional): Options to pass to mount(8).
  - **`mount_point`** (*string*, Required): Path on the filesystem to mount.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the machine.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to mount the special filesystem on this machine.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-override_failed_testing: Ignore failed tests

  Ignore failed tests and put node back into a usable state.

  **Operation ID:** `MachineHandler_override_failed_testing`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 

  **Request body (multipart/form-data):**

  - **`comment`** (*string*, Optional): Comment for the event log.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The user is not authorized to override tests.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-power_off: Power off a node

  Powers off a given node.

  **Operation ID:** `MachineHandler_power_off`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 

  **Request body (multipart/form-data):**

  - **`comment`** (*string*, Optional): Comment for the event log.
  - **`stop_mode`** (*string*, Optional): Power-off mode. If 'soft', perform a soft power down if the node's power type supports it, otherwise perform a hard power off. For all values other than 'soft', and by default, perform a hard power off. A soft power off generally asks the OS to shutdown the system gracefully before powering off, while a hard power off occurs immediately without any warning to the OS.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  A JSON object containing the node's information.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user is not authorized to power off the node.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-power_on: Turn on a node

  Turn on the given node with optional user-data and comment.

  **Operation ID:** `MachineHandler_power_on`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 

  **Request body (multipart/form-data):**

  - **`comment`** (*string*, Optional): Comment for the event log.
  - **`user_data`** (*string*, Optional): Base64-encoded blob of data to be made available to the nodes through the metadata service.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  A JSON object containing the node's information.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user is not authorized to power on the node.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

  **HTTP 503 SERVICE UNAVAILABLE**
  
  Returns 503 if the start-up attempted to allocate an IP address, and there were no IP addresses available on the relevant cluster interface.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/machines/{system_id}/op-power_parameters: Get power parameters

  Gets power parameters for a given system_id, if any. For some types of power control this will include private information such as passwords and secret keys.
Note that this method is reserved for admin users and returns a 403 if the user is not one.

  **Operation ID:** `MachineHandler_power_parameters`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 

  **Responses:**

  **HTTP 200 OK**
  
  200

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to see the power parameters.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/machines/{system_id}/op-query_power_state: Get the power state of a node

  Gets the power state of a given node. MAAS sends a request to the node's power controller, which asks it about the node's state.
The reply to this could be delayed by up to 30 seconds while waiting for the power controller to respond.  Use this method sparingly as it ties up an appserver thread while waiting.

  **Operation ID:** `MachineHandler_query_power_state`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The node to query.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the node's power state.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-release: Release a machine

  Releases a machine with the given system_id. Note that this operation is the opposite of allocating a machine.
*Erasing drives*:
If neither `secure_erase` nor `quick_erase` are specified, MAAS will overwrite the whole disk with null bytes. This can be very slow.
If both `secure_erase` and `quick_erase` are specified and the drive does NOT have a secure erase feature, MAAS will behave as if only `quick_erase` was specified.
If `secure_erase` is specified and `quick_erase` is NOT specified and the drive does NOT have a secure erase feature, MAAS will behave as if `secure_erase` was NOT specified, i.e. MAAS will overwrite the whole disk with null bytes. This can be very slow.

  **Operation ID:** `MachineHandler_release`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machines's system_id.

  **Request body (multipart/form-data):**

  - **`comment`** (*string*, Optional): Optional comment for the event log.
  - **`erase`** (*boolean*, Optional): Erase the disk when releasing.
  - **`force`** (*boolean*, Optional): Will force the release of a machine. If the machine was deployed as a KVM host, this will be deleted as well as all machines inside the KVM host. USE WITH CAUTION.
  - **`quick_erase`** (*boolean*, Optional): Wipe 2MiB at the start and at the end of the drive to make data recovery inconvenient and unlikely to happen by accident. This is not secure.
  - **`secure_erase`** (*boolean*, Optional): Use the drive's secure erase feature if available. In some cases, this can be much faster than overwriting the drive. Some drives implement secure erasure by overwriting themselves so this could still be slow.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the released machine.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to release this machine.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The machine is in a state that prevents it from being released.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-rescue_mode: Enter rescue mode

  Begins the rescue mode process on a machine with the given system_id.
A machine in the 'deployed' or 'broken' state may initiate the rescue mode process.

  **Operation ID:** `MachineHandler_rescue_mode`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machines's system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the machine information.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to begin rescue mode on the machine.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-restore_default_configuration: Restore default configuration

  Restores the default configuration options on a machine with the given system_id.

  **Operation ID:** `MachineHandler_restore_default_configuration`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machines's system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the machine information.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to restore default options on this machine.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-restore_networking_configuration: Restore networking options

  Restores networking options to their initial state on a machine with the given system_id.

  **Operation ID:** `MachineHandler_restore_networking_configuration`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machines's system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the machine information.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to restore networking options on this machine.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-restore_storage_configuration: Restore storage configuration

  Restores storage configuration options to their initial state on a machine with the given system_id.

  **Operation ID:** `MachineHandler_restore_storage_configuration`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machines's system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the machine information.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to restore storage options on this machine.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} ~~POST /MAAS/api/2.0/machines/{system_id}/op-set_owner_data: Deprecated, use set-workload-annotations.~~

  Deprecated, use set-workload-annotations instead.

  ```{warning}
  This endpoint is deprecated.
  ```

  **Operation ID:** `MachineHandler_set_owner_data`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The user does not have set the zone.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-set_storage_layout: Change storage layout

  Changes the storage layout on machine with the given system_id.
This operation can only be performed on a machine with a status of 'Ready'.
Note: This will clear the current storage layout and any extra configuration and replace it will the new layout.

  **Operation ID:** `MachineHandler_set_storage_layout`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machines's system_id.

  **Request body (multipart/form-data):**

  - **`boot_size`** (*string*, Optional): Size of the boot partition (e.g. 512M, 1G).
  - **`cache_device`** (*string*, Optional): Bcache only. Physical block device to use as the cache device (e.g. /dev/sda).
  - **`cache_mode`** (*string*, Optional): Bcache only. Cache mode for bcache device: `writeback`, `writethrough`, `writearound`.
  - **`cache_no_part`** (*boolean*, Optional): Bcache only. Don't create a partition on the cache device. Use the entire disk as the cache device.
  - **`cache_size`** (*string*, Optional): Bcache only. Size of the cache partition to create on the cache device (e.g. 48G).
  - **`lv_name`** (*string*, Optional): LVM only. Name of created logical volume.
  - **`lv_size`** (*string*, Optional): LVM only. Size of created logical volume.
  - **`root_device`** (*string*, Optional): Physical block device to place the root partition (e.g. /dev/sda).
  - **`root_size`** (*string*, Optional): Size of the root partition (e.g. 24G).
  - **`storage_layout`** (*string*, Required): Storage layout for the machine: `flat`, `lvm`, `bcache`, `vmfs6`, `vmfs7`, `custom` or `blank`.
  - **`vg_name`** (*string*, Optional): LVM only. Name of created volume group.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the machine.
  
  Content type: `application/json`

  **HTTP 400 BAD REQUEST**
  
  The requested machine is not allocated.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to set the storage layout of this machine.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-set_workload_annotations: Set key=value data

  Set key=value data for the current owner.
Pass any key=value form data to this method to add, modify, or remove.
A key is removed when the value for that key is set to an empty string.
This operation will not remove any previous keys unless explicitly passed with an empty string. All workload annotations are removed when the machine is no longer allocated to a user.

  **Operation ID:** `MachineHandler_set_workload_annotations`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 

  **Request body (multipart/form-data):**

  - **`key`** (*string*, Required): `key` can be any string value.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The user does not have set the zone.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-test: Begin testing process for a node

  Begins the testing process for a given node.
A node in the 'ready', 'allocated', 'deployed', 'broken', or any failed state may run tests. If testing is started and successfully passes from 'broken' or any failed state besides 'failed commissioning' the node will be returned to a ready state. Otherwise the node will return to the state it was when testing started.

  **Operation ID:** `MachineHandler_test`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 

  **Request body (multipart/form-data):**

  - **`enable_ssh`** (*integer*, Optional): Whether to enable SSH for the testing environment using the user's SSH key(s). 0 = false. 1 = true.
  - **`parameters`** (*string*, Optional): Scripts selected to run may define their own parameters. These parameters may be passed using the parameter name. Optionally a parameter may have the script name prepended to have that parameter only apply to that specific script.
  - **`testing_scripts`** (*string*, Optional): A comma-separated list of testing script names and tags to be run. By default all tests tagged 'commissioning' will be run.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  A JSON object containing the node's information.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-unlock: Unlock a machine

  Mark a machine with the given system_id as 'Unlocked' to allow changes.

  **Operation ID:** `MachineHandler_unlock`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machines's system_id.

  **Request body (multipart/form-data):**

  - **`comment`** (*string*, Optional): Optional comment for the event log.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the machine information.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to unlock the machine.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/{system_id}/op-unmount_special: Unmount a special-purpose filesystem

  Unmount a special-purpose filesystem, like tmpfs, on a machine with the given system_id.

  **Operation ID:** `MachineHandler_unmount_special`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machines's system_id.

  **Request body (multipart/form-data):**

  - **`mount_point`** (*string*, Required): Path on the filesystem to unmount.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the machine.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to unmount the special filesystem on this machine.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

## Machines

Operations for machines resources.

````{dropdown} GET /MAAS/api/2.0/machines/: List Nodes visible to the user

  List nodes visible to current user, optionally filtered by criteria.
Nodes are sorted by id (i.e. most recent last) and grouped by type.

  **Operation ID:** `MachinesHandler_read`

  **Parameters:**

  - **`hostname`** (*string*, Optional): Only nodes relating to the node with the matching hostname will be returned. This can be specified multiple times to see multiple nodes.
  - **`cpu_count`** (*integer*, Optional): Only nodes with the specified minimum number of CPUs will be included.
  - **`mem`** (*string*, Optional): Only nodes with the specified minimum amount of RAM (in MiB) will be included.
  - **`mac_address`** (*string*, Optional): Only nodes relating to the node owning the specified MAC address will be returned. This can be specified multiple times to see multiple nodes.
  - **`id`** (*string*, Optional): Only nodes relating to the nodes with matching system ids will be returned.
  - **`domain`** (*string*, Optional): Only nodes relating to the nodes in the domain will be returned.
  - **`zone`** (*string*, Optional): Only nodes relating to the nodes in the zone will be returned.
  - **`pool`** (*string*, Optional): Only nodes belonging to the pool will be returned.
  - **`agent_name`** (*string*, Optional): Only nodes relating to the nodes with matching agent names will be returned.
  - **`fabrics`** (*string*, Optional): Only nodes with interfaces in specified fabrics will be returned.
  - **`not_fabrics`** (*string*, Optional): Only nodes with interfaces not in specified fabrics will be returned.
  - **`vlans`** (*string*, Optional): Only nodes with interfaces in specified VLANs will be returned.
  - **`not_vlans`** (*string*, Optional): Only nodes with interfaces not in specified VLANs will be returned.
  - **`subnets`** (*string*, Optional): Only nodes with interfaces in specified subnets will be returned.
  - **`not_subnets`** (*string*, Optional): Only nodes with interfaces not in specified subnets will be returned.
  - **`link_speed`** (*string*, Optional): Only nodes with interfaces with link speeds greater than or equal to link_speed will be returned.
  - **`status`** (*string*, Optional): Only nodes with specified status will be returned.
  - **`pod`** (*string*, Optional): Only nodes that belong to a specified pod will be returned.
  - **`not_pod`** (*string*, Optional): Only nodes that don't belong to a specified pod will be returned.
  - **`pod_type`** (*string*, Optional): Only nodes that belong to a pod of the specified type will be returned.
  - **`not_pod_type`** (*string*, Optional): Only nodes that don't belong to a pod of the specified type will be returned.
  - **`devices`** (*string*, Optional): Only return nodes which have one or more devices containing the following constraints in the format key=value[,key2=value2[,.] Each key can be one of the following: - `vendor_id`: The device vendor id - `product_id`: The device product id - `vendor_name`: The device vendor name, not case sensative - `product_name`: The device product name, not case sensative - `commissioning_driver`: The device uses this driver during commissioning.
  - **`arch`** (*string*, Optional): Only nodes with the specified architecture will be returned.
  - **`not_arch`** (*string*, Optional): Only nodes without the specified architecture will be returned.
  - **`cpu_speed`** (*string*, Optional): Only nodes with CPUs running at the specified speed (in MHz) will be returned.
  - **`deployment_target`** (*string*, Optional): Only nodes with the specified deployment target will be returned.
  - **`not_deployment_target`** (*string*, Optional): Only nodes without the specified deployment target will be returned.
  - **`fabric_classes`** (*string*, Optional): Attached to fabric with specified classes.
  - **`not_fabric_classes`** (*string*, Optional): Not attached to fabric with specified classes.
  - **`interfaces`** (*string*, Optional): Only nodes with interfaces matching the specified constraints will be returned.
  - **`not_hostname`** (*string*, Optional): Hostnames to ignore.
  - **`not_id`** (*string*, Optional): System IDs to ignore.
  - **`not_domain`** (*string*, Optional): Domain names to ignore.
  - **`not_agent_name`** (*string*, Optional): Excludes nodes with events matching the agent name.
  - **`not_in_pool`** (*string*, Optional): Only nodes not in the specified resource pools will be returned.
  - **`not_in_zone`** (*string*, Optional): Not in zone.
  - **`not_owner`** (*string*, Optional): Only nodes not owned by the specified users will be returned.
  - **`not_power_state`** (*string*, Optional): Only nodes not in the specified power states will be returned.
  - **`not_simple_status`** (*string*, Optional): Exclude nodes with the specified simplified status.
  - **`not_status`** (*string*, Optional): Exclude nodes with the specified status.
  - **`not_tags`** (*string*, Optional): Not having tags.
  - **`owner`** (*string*, Optional): Only nodes owned by the specified users will be returned.
  - **`power_state`** (*string*, Optional): Only nodes in the specified power states will be returned.
  - **`simple_status`** (*string*, Optional): Only includes nodes with the specified simplified status.
  - **`storage`** (*string*, Optional): Only nodes with storage matching the specified constraints will be returned.
  - **`system_id`** (*string*, Optional): Only nodes with the specified system IDs will be returned.
  - **`tags`** (*string*, Optional): Only nodes with the specified tags will be returned.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of node objects.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/machines/: Create a new machine

  Create a new machine.
Adding a server to MAAS will (by default) cause the machine to network boot into an ephemeral environment to collect hardware information.
In anonymous enlistment (and when the enlistment is done by a non-admin), the machine is held in the "New" state for approval by a MAAS admin.
The minimum data required is:
architecture=<arch string> (e.g. "i386/generic") mac_addresses=<value> (e.g. "aa:bb:cc:dd:ee:ff")

  **Operation ID:** `MachinesHandler_create`

  **Request body (multipart/form-data):**

  - **`architecture`** (*string*, Required): A string containing the architecture type of the machine. (For example, "i386", or "amd64".) To :type architecture: unicode
  - **`commission`** (*boolean*, Optional): Request the newly created machine to be created with status set to COMMISSIONING. Machines will wait for COMMISSIONING results and not time out. Machines created by administrators will be commissioned unless set to false.
  - **`commissioning_scripts`** (*string*, Optional): A comma seperated list of commissioning script names and tags to be run. By default all custom commissioning scripts are run. Built-in commissioning scripts always run. Selecting 'update_firmware' or 'configure_hba' will run firmware updates or configure HBA's on matching machines.
  - **`deployed`** (*boolean*, Optional): Request the newly created machine to be created with status set to DEPLOYED. Setting this to true implies commissioning=false, meaning that the machine won't go through the commissioning process.
  - **`description`** (*string*, Optional): A optional description.
  - **`domain`** (*string*, Optional): The domain of the machine. If not given the default domain is used.
  - **`enable_ssh`** (*integer*, Optional): Whether to enable SSH for the commissioning environment using the user's SSH key(s). '1' = True, '0' = False.
  - **`hostname`** (*string*, Optional): A hostname. If not given, one will be generated.
  - **`is_dpu`** (*boolean*, Optional): Whether the machine is a DPU or not. If not provided, the machine is considered a non-DPU machine.
  - **`mac_addresses`** (*string*, Required): One or more MAC addresses for the machine. To specify more than one MAC address, the parameter must be specified twice. (such as "machines new mac_addresses=01:02:03:04:05:06 mac_addresses=02:03:04:05:06:07")
  - **`min_hwe_kernel`** (*string*, Optional): A string containing the minimum kernel version allowed to be ran on this machine.
  - **`power_parameters_{param}`** (*string*, Optional): The parameter(s) for the power_type. Note that this is dynamic as the available parameters depend on the selected value of the Machine's power_type. `Power types`_ section for a list of the available power parameters for each power type.
  - **`power_type`** (*string*, Optional): A power management type, if applicable (e.g. "virsh", "ipmi").
  - **`skip_bmc_config`** (*integer*, Optional): Whether to skip re-configuration of the BMC for IPMI based machines. '1' = True, '0' = False.
  - **`skip_networking`** (*integer*, Optional): Whether to skip re-configuring the networking on the machine after the commissioning has completed. '1' = True, '0' = False.
  - **`skip_storage`** (*integer*, Optional): Whether to skip re-configuring the storage on the machine after the commissioning has completed. '1' = True, '0' = False.
  - **`subarchitecture`** (*string*, Optional): A string containing the subarchitecture type of the machine. (For example, "generic" or "hwe-t".) To determine the supported subarchitectures, use the boot-resources endpoint.
  - **`testing_scripts`** (*string*, Optional): A comma seperated list of testing script names and tags to be run. By default all tests tagged 'commissioning' will be run. Set to 'none' to disable running tests.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the machine information.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/machines/op-accept: Accept declared machines

  Accept declared machines into MAAS.
Machines can be enlisted in the MAAS anonymously or by non-admin users, as opposed to by an admin.  These machines are held in the New state; a MAAS admin must first verify the authenticity of these enlistments, and accept them.
Enlistments can be accepted en masse, by passing multiple machines to this call.  Accepting an already accepted machine is not an error, but accepting one that is already allocated, broken, etc. is.

  **Operation ID:** `MachinesHandler_accept`

  **Request body (multipart/form-data):**

  - **`machines`** (*string*, Optional): A list of system_ids of the machines whose enlistment is to be accepted. (An empty list is acceptable).

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of accepted machines.
  
  Content type: `application/json`

  **HTTP 400 BAD REQUEST**
  
  One or more of the given machines is not found.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to accept machines.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/op-accept_all: Accept all declared machines

  Accept all declared machines into MAAS.
Machines can be enlisted in the MAAS anonymously or by non-admin users, as opposed to by an admin.  These machines are held in the New state; a MAAS admin must first verify the authenticity of these enlistments, and accept them.

  **Operation ID:** `MachinesHandler_accept_all`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of accepted machines.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/machines/op-add_chassis: Add special hardware

  Add special hardware types.

  **Operation ID:** `MachinesHandler_add_chassis`

  **Request body (multipart/form-data):**

  - **`accept_all`** (*string*, Optional): If true, all enlisted machines will be commissioned.
  - **`chassis_type`** (*string*, Required): The type of hardware: - `hmcz`: IBM Hardware Management Console (HMC) for Z - `mscm`: Moonshot Chassis Manager. - `msftocs`: Microsoft OCS Chassis Manager. - `powerkvm`: Virtual Machines on Power KVM, managed by Virsh. - `proxmox`: Virtual Machines managed by Proxmox - `recs_box`: Christmann RECS|Box servers. - `sm15k`: Seamicro 1500 Chassis. - `ucsm`: Cisco UCS Manager. - `virsh`: virtual machines managed by Virsh. - `vmware` is the type for virtual machines managed by VMware.
  - **`domain`** (*string*, Optional): The domain that each new machine added should use.
  - **`hostname`** (*string*, Required): The URL, hostname, or IP address to access the chassis.
  - **`password`** (*string*, Optional): The password used to access the chassis. This field is required for the `recs_box`, `seamicro15k`, `vmware`, `mscm`, `msftocs`, `ucsm`, and `hmcz` chassis types.
  - **`port`** (*integer*, Optional): (`recs_box`, `vmware`, `msftocs` only) The port to use when accessing the chassis. The following are optional if you are adding a vmware chassis:
  - **`power_control`** (*string*, Optional): (`seamicro15k` only) The power_control to use, either ipmi (default), restapi, or restapi2. The following are optional if you are adding a proxmox chassis.
  - **`prefix_filter`** (*string*, Optional): (`virsh`, `vmware`, `powerkvm`, `proxmox`, `hmcz` only.) Filter machines with supplied prefix.
  - **`protocol`** (*string*, Optional): (`vmware` only) The protocol to use when accessing the VMware chassis (default: https). :return: A string containing the chassis powered on by which rack controller.
  - **`rack_controller`** (*string*, Optional): The system_id of the rack controller to send the add chassis command through. If none is specifed MAAS will automatically determine the rack controller to use.
  - **`token_name`** (*string*, Optional): The name the authentication token to be used instead of a password.
  - **`token_secret`** (*string*, Optional): The token secret to be used in combination with the power_token_name used in place of a password.
  - **`username`** (*string*, Optional): The username used to access the chassis. This field is required for the recs_box, seamicro15k, vmware, mscm, msftocs, ucsm, and hmcz chassis types.
  - **`verify_ssl`** (*boolean*, Optional): Whether SSL connections should be verified. The following are optional if you are adding a recs_box, vmware or msftocs chassis.

  **Responses:**

  **HTTP 200 OK**
  
  Asking maas-run to add machines from chassis
  
  Content type: `text/plain`

  **HTTP 400 BAD REQUEST**
  
  Required parameters are missing.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to access the rack controller.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  No rack controller can be found that has access to the given URL.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/op-allocate: Allocate a machine

  Allocates an available machine for deployment.
Constraints parameters can be used to allocate a machine that possesses certain characteristics.  All the constraints are optional and when multiple constraints are provided, they are combined using 'AND' semantics.

  **Operation ID:** `MachinesHandler_allocate`

  **Request body (multipart/form-data):**

  - **`agent_name`** (*string*, Optional): An optional agent name to attach to the acquired machine.
  - **`arch`** (*string*, Optional): Architecture of the returned machine (e.g. 'i386/generic', 'amd64', 'armhf/highbank', etc.). If multiple architectures are specified, the machine to acquire may match any of the given architectures. To request multiple architectures, this parameter must be repeated in the request with each value.
  - **`bridge_all`** (*boolean*, Optional): Optionally create a bridge interface for every configured interface on the machine. The created bridges will be removed once the machine is released. (Default: False)
  - **`bridge_fd`** (*integer*, Optional): Optionally adjust the forward delay to time seconds. (Default: 15)
  - **`bridge_stp`** (*boolean*, Optional): Optionally turn spanning tree protocol on or off for the bridges created on every configured interface. (Default: off)
  - **`comment`** (*string*, Optional): Comment for the event log.
  - **`cpu_count`** (*integer*, Optional): Minimum number of CPUs a returned machine must have. A machine with additional CPUs may be allocated if there is no exact match, or if the 'mem' constraint is not also specified.
  - **`devices`** (*string*, Optional): Only return a node which have one or more devices containing the following constraints in the format key=value[,key2=value2[,.] Each key can be one of the following: - `vendor_id`: The device vendor id - `product_id`: The device product id - `vendor_name`: The device vendor name, not case sensative - `product_name`: The device product name, not case sensative - `commissioning_driver`: The device uses this driver during commissioning.
  - **`dry_run`** (*boolean*, Optional): Optional boolean to indicate that the machine should not actually be acquired (this is for support/troubleshooting, or users who want to see which machine would match a constraint, without acquiring a machine). Defaults to False.
  - **`fabric_classes`** (*string*, Optional): Set of fabric class types whose fabrics the machine must be associated with in order to be acquired. If multiple fabrics class types are specified, the machine can be in any matching fabric. To request multiple possible fabrics class types to match, this parameter must be repeated in the request with each value.
  - **`fabrics`** (*string*, Optional): Set of fabrics that the machine must be associated with in order to be acquired. If multiple fabrics names are specified, the machine can be in any of the specified fabrics. To request multiple possible fabrics to match, this parameter must be repeated in the request with each value.
  - **`interfaces`** (*string*, Optional): A labeled constraint map associating constraint labels with interface properties that should be matched. Returned nodes must have one or more interface matching the specified constraints. The labeled constraint map must be in the format: `label:key=value[,key2=value2[,.]`. Each key can be one of the following: - `id`: Matches an interface with the specific id - `fabric`: Matches an interface attached to the specified fabric. - `fabric_class`: Matches an interface attached to a fabric with the specified class. - `ip`: Matches an interface with the specified IP address assigned to it. - `mode`: Matches an interface with the specified mode. (Currently, the only supported mode is "unconfigured".) - `name`: Matches an interface with the specified name. (For example, "eth0".) - `hostname`: Matches an interface attached to the node with the specified hostname. - `subnet`: Matches an interface attached to the specified subnet. - `space`: Matches an interface attached to the specified space. - `subnet_cidr`: Matches an interface attached to the specified subnet CIDR. (For example, "192.168.0.0/24".) - `type`: Matches an interface of the specified type. (Valid types: "physical", "vlan", "bond", "bridge", or "unknown".) - `vlan`: Matches an interface on the specified VLAN. - `vid`: Matches an interface on a VLAN with the specified VID. - `tag`: Matches an interface tagged with the specified tag. - `link_speed`: Matches an interface with link_speed equal to or greater than the specified speed.
  - **`mem`** (*integer*, Optional): The minimum amount of memory (expressed in MB) the returned machine must have. A machine with additional memory may be allocated if there is no exact match, or the 'cpu_count' constraint is not also specified.
  - **`name`** (*string*, Optional): Hostname or FQDN of the desired machine. If a FQDN is specified, both the domain and the hostname portions must match.
  - **`not_fabric_classes`** (*string*, Optional): Fabric class types whose fabrics the machine must NOT be associated with in order to be acquired. If multiple fabrics names are specified, the machine must NOT be in ANY of them. To request exclusion of multiple fabrics, this parameter must be repeated in the request with each value.
  - **`not_fabrics`** (*string*, Optional): Fabrics the machine must NOT be associated with in order to be acquired. If multiple fabrics names are specified, the machine must NOT be in ANY of them. To request exclusion of multiple fabrics, this parameter must be repeated in the request with each value.
  - **`not_in_pool`** (*string*, Optional): List of resource pool from which the machine must not be acquired. If multiple pools are specified, the machine must NOT be associated with ANY of them. To request multiple pools to exclude, this parameter must be repeated in the request with each value.
  - **`not_in_zone`** (*string*, Optional): List of physical zones from which the machine must not be acquired. If multiple zones are specified, the machine must NOT be associated with ANY of them. To request multiple zones to exclude, this parameter must be repeated in the request with each value.
  - **`not_pod`** (*string*, Optional): Pod the machine must not be located in.
  - **`not_pod_type`** (*string*, Optional): Pod type the machine must not be located in.
  - **`not_subnets`** (*string*, Optional): Subnets that must NOT be linked to the machine. See the 'subnets' constraint documentation above for more information about how each subnet can be specified. If multiple subnets are specified, the machine must NOT be associated with ANY of them. To request multiple subnets to exclude, this parameter must be repeated in the request with each value. (Or a fabric, space, or VLAN specifier may be used to match multiple subnets). Note that this replaces the legacy 'not_networks' constraint in MAAS 1.x.
  - **`not_tags`** (*string*, Optional): Tags the machine must NOT match. If multiple tag names are specified, the machine must NOT be tagged with ANY of them. To request exclusion of multiple tags, this parameter must be repeated in the request with each value.
  - **`pod`** (*string*, Optional): Pod the machine must be located in.
  - **`pod_type`** (*string*, Optional): Pod type the machine must be located in.
  - **`pool`** (*string*, Optional): Resource pool name the machine must belong to.
  - **`storage`** (*string*, Optional): A list of storage constraint identifiers, in the form: `label:size(tag[,tag[,.])][,label:.]`.
  - **`subnets`** (*string*, Optional): Subnets that must be linked to the machine. "Linked to" means the node must be configured to acquire an address in the specified subnet, have a static IP address in the specified subnet, or have been observed to DHCP from the specified subnet during commissioning time (which implies that it *could* have an address on the specified subnet). Subnets can be specified by one of the following criteria: - <id>: Match the subnet by its + `id` field - fabric:<fabric-spec>: Match all subnets in a given fabric. - ip:<ip-address>: Match the subnet containing <ip-address> with the with the longest-prefix match. - name:<subnet-name>: Match a subnet with the given name. - space:<space-spec>: Match all subnets in a given space. - vid:<vid-integer>: Match a subnet on a VLAN with the specified VID. Valid values range from 0 through 4094 (inclusive). An untagged VLAN can be specified by using the value "0". - vlan:<vlan-spec>: Match all subnets on the given VLAN. Note that (as of this writing), the 'fabric', 'space', 'vid', and.
  + `vlan` specifiers are only useful for the.
  + `not_spaces` version of this constraint, because they will most likely force the query to match ALL the subnets in each fabric, space, or VLAN, and thus not return any nodes. (This is not a particularly useful behavior, so may be changed in the future.) If multiple subnets are specified, the machine must be associated with all of them. To request multiple subnets, this parameter must be repeated in the request with each value. Note that this replaces the legacy.
  + `networks` constraint in MAAS 1.x.
  - **`system_id`** (*string*, Optional): system_id of the desired machine.
  - **`tags`** (*string*, Optional): Tags the machine must match in order to be acquired. If multiple tag names are specified, the machine must be tagged with all of them. To request multiple tags, this parameter must be repeated in the request with each value.
  - **`verbose`** (*boolean*, Optional): Optional boolean to indicate that the user would like additional verbosity in the constraints_by_type field (each constraint will be prefixed by `verbose_`, and contain the full data structure that indicates which machine(s) matched).
  - **`zone`** (*string*, Optional): Physical zone name the machine must be located in.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a newly allocated machine object.
  
  Content type: `application/json`

  **HTTP 409 CONFLICT**
  
  No machine matching the given constraints could be found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/op-clone: Clone storage and/or interface configurations

  Clone storage and/or interface configurations A machine storage and/or interface configuration can be cloned to a set of destination machines.
For storage configuration, cloning the destination machine must have at least the same number of physical block devices or more, along with the physical block devices being the same size or greater.
For interface configuration, cloning the destination machine must have at least the same number of interfaces with the same names. The destination machine can have more interfaces than the source, as long as the subset of interfaces on the destination have the same matching names as the source.

  **Operation ID:** `MachinesHandler_clone`

  **Request body (multipart/form-data):**

  - **`destinations`** (*string*, Required): A list of system_ids to clone the configuration to.
  - **`interfaces`** (*boolean*, Required): Whether to clone interface configuration. Defaults to False.
  - **`source`** (*string*, Required): The system_id of the machine that is the source of the configuration.
  - **`storage`** (*boolean*, Required): Whether to clone storage configuration. Defaults to False.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 400 BAD REQUEST**
  
  Source and/or destinations are not found.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user not authenticated.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/machines/op-is_registered: MAC address registered

  Returns whether or not the given MAC address is registered within this MAAS (and attached to a non-retired node).

  **Operation ID:** `MachinesHandler_is_registered`

  **Parameters:**

  - **`mac_address`** (*object*, Required): The MAC address to be checked.

  **Responses:**

  **HTTP 200 OK**
  
  'true' or 'false'

  **HTTP 400 BAD REQUEST**
  
  mac_address was missing
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/machines/op-list_allocated: List allocated

  List machines that were allocated to the User.

  **Operation ID:** `MachinesHandler_list_allocated`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of allocated machines.
  
  Content type: `application/json`

````

````{dropdown} GET /MAAS/api/2.0/machines/op-power_parameters: Get power parameters

  Get power parameters for multiple machines. To request power parameters for a specific machine or more than one machine:
`op=power_parameters&id=abc123&id=def456`.

  **Operation ID:** `MachinesHandler_power_parameters`

  **Parameters:**

  - **`id`** (*object*, Required): A system ID. To request more than one machine, provide multiple `id` arguments in the request. Only machines with matching system ids will be returned.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of power parameters with system_ids as keys.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user is not authorized to view the power parameters.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/op-release: Release machines

  Release multiple machines. Places the machines back into the pool, ready to be reallocated.

  **Operation ID:** `MachinesHandler_release`

  **Request body (multipart/form-data):**

  - **`comment`** (*string*, Optional): Optional comment for the event log.
  - **`machines`** (*string*, Required): A list of system_ids of the machines which are to be released. (An empty list is acceptable).

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of release machines.
  
  Content type: `application/json`

  **HTTP 400 BAD REQUEST**
  
  One or more of the given machines is not found.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to release machines.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The current state of the machine prevents it from being released.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/machines/op-set_zone: Assign nodes to a zone

  Assigns a given node to a given zone.

  **Operation ID:** `MachinesHandler_set_zone`

  **Request body (multipart/form-data):**

  - **`nodes`** (*string*, Required): The node to add.
  - **`zone`** (*string*, Required): The zone name.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 400 BAD REQUEST**
  
  The given parameters were not correct.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user does not have set the zone.
  
  Content type: `text/plain`

````

## Network (deprecated)

Operations for network (deprecated) resources.

````{dropdown} ~~DELETE /MAAS/api/2.0/networks/{name}/: NetworkHandler delete~~

  Manage a network.
The 'Network' endpoint has been deprecated in favour of 'Subnet'.

  ```{warning}
  This endpoint is deprecated.
  ```

  **Operation ID:** `NetworkHandler_delete`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested subnet is not found.
  
  Content type: `text/plain`

````

````{dropdown} ~~GET /MAAS/api/2.0/networks/{name}/: NetworkHandler read~~

  Manage a network.
The 'Network' endpoint has been deprecated in favour of 'Subnet'.

  ```{warning}
  This endpoint is deprecated.
  ```

  **Operation ID:** `NetworkHandler_read`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the subnet.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested subnet is not found.
  
  Content type: `text/plain`

````

````{dropdown} ~~PUT /MAAS/api/2.0/networks/{name}/: NetworkHandler update~~

  Manage a network.
The 'Network' endpoint has been deprecated in favour of 'Subnet'.

  ```{warning}
  This endpoint is deprecated.
  ```

  **Operation ID:** `NetworkHandler_update`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the updated subnet.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested subnet is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/networks/{name}/op-connect_macs: NetworkHandler connect_macs

  Manage a network.
The 'Network' endpoint has been deprecated in favour of 'Subnet'.

  **Operation ID:** `NetworkHandler_connect_macs`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 

  **Responses:**

  **HTTP 404 NOT FOUND**
  
  Service layer not initialized in this thread. This is likely to be a programming error and should never happen.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/networks/{name}/op-disconnect_macs: NetworkHandler disconnect_macs

  Manage a network.
The 'Network' endpoint has been deprecated in favour of 'Subnet'.

  **Operation ID:** `NetworkHandler_disconnect_macs`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 

  **Responses:**

  **HTTP 404 NOT FOUND**
  
  Service layer not initialized in this thread. This is likely to be a programming error and should never happen.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/networks/{name}/op-list_connected_macs: NetworkHandler list_connected_macs

  Manage a network.
The 'Network' endpoint has been deprecated in favour of 'Subnet'.

  **Operation ID:** `NetworkHandler_list_connected_macs`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 

  **Responses:**

  **HTTP 404 NOT FOUND**
  
  connection to server on socket "/home/maik.rebaum@canonical.com/src/maas/db/.s.PGSQL.5432" failed: No such file or directory
	Is the server running locally and accepting connections on that socket?

  
  Content type: `text/plain`

````

## Networks (deprecated)

Operations for networks (deprecated) resources.

````{dropdown} ~~GET /MAAS/api/2.0/networks/: NetworksHandler read~~

  Manage the networks.
The 'Networks' endpoint has been deprecated in favour of 'Subnets'.

  ```{warning}
  This endpoint is deprecated.
  ```

  **Operation ID:** `NetworksHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing list of all known subnets.
  
  Content type: `application/json`

````

````{dropdown} ~~POST /MAAS/api/2.0/networks/: NetworksHandler create~~

  Manage the networks.
The 'Networks' endpoint has been deprecated in favour of 'Subnets'.

  ```{warning}
  This endpoint is deprecated.
  ```

  **Operation ID:** `NetworksHandler_create`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the new subnet.
  
  Content type: `application/json`

````

## Node

Operations for node resources.

````{dropdown} DELETE /MAAS/api/2.0/nodes/{system_id}/: Delete a node

  Deletes a node with a given system_id.

  **Operation ID:** `NodeHandler_delete`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A node's system_id.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The user is not authorized to delete the node.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/: Read a node

  Reads a node with the given system_id.

  **Operation ID:** `NodeHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A node's system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the requested node.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/op-details: Get system details

  Returns system details - for example, LLDP and `lshw` XML dumps.
Returns a `{detail_type: xml, .}` map, where `detail_type` is something like "lldp" or "lshw".
Note that this is returned as BSON and not JSON. This is for efficiency, but mainly because JSON can't do binary content without applying additional encoding like base-64. The example output below is represented in ASCII using `bsondump example.bson` and is for demonstrative purposes.

  **Operation ID:** `NodeHandler_details`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The node's system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A BSON object represented here in ASCII using `bsondump example.bson`.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to see the node details.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/op-power_parameters: Get power parameters

  Gets power parameters for a given system_id, if any. For some types of power control this will include private information such as passwords and secret keys.
Note that this method is reserved for admin users and returns a 403 if the user is not one.

  **Operation ID:** `NodeHandler_power_parameters`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 

  **Responses:**

  **HTTP 200 OK**
  
  200

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to see the power parameters.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

## Node Device

Operations for node device resources.

````{dropdown} DELETE /MAAS/api/2.0/nodes/{system_id}/devices/{id}/: Delete a node device

  Delete a node device with the given system_id and id.
If the device is still present in the system it will be recreated when the node is commissioned.

  **Operation ID:** `NodeDeviceHandler_delete`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A system_id
  - **`{id}`** (*string*, path parameter, Required): A node device id.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested node or node device is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/devices/{id}/: Return a specific node device

  Return a node device with the given system_id and node device id.

  **Operation ID:** `NodeDeviceHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A system_id.
  - **`{id}`** (*integer*, path parameter, Required): A node device id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new requested node device object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested node or node device is not found.
  
  Content type: `text/plain`

````

## Node Devices

Operations for node devices resources.

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/devices/: Return node devices

  Return a list of devices attached to the node given by a system_id.

  **Operation ID:** `NodeDevicesHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The node's system_id.
  - **`bus`** (*string*, Optional): Only return devices attached to the specified bus. Can be PCIE or USB. Defaults to all.
  - **`hardware_type`** (*string*, Optional): Only return scripts for the given hardware type. Can be `node`, `cpu`, `memory`, `storage` or `gpu`. Defaults to all.
  - **`vendor_id`** (*string*, Optional): Only return devices which have the specified vendor id.
  - **`product_id`** (*string*, Optional): Only return devices which have the specified product id.
  - **`vendor_name`** (*string*, Optional): Only return devices which have the specified vendor_name.
  - **`product_name`** (*string*, Optional): Only return devices which have the specified product_name.
  - **`commissioning_driver`** (*string*, Optional): Only return devices which use the specified driver when commissioning.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of script result objects.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

## Node Script

Operations for node script resources.

````{dropdown} DELETE /MAAS/api/2.0/scripts/{name}: Delete a script

  Deletes a script with the given name.

  **Operation ID:** `NodeScriptHandler_delete`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 
  - **`{name}`** (*string*, path parameter, Required): The script's name.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested script is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/scripts/{name}: Return script metadata

  Return metadata belonging to the script with the given name.

  **Operation ID:** `NodeScriptHandler_read`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 
  - **`{name}`** (*string*, path parameter, Required): The script's name.
  - **`include_script`** (*string*, Optional): Include the base64 encoded script content if any value is given for include_script.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the script.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested script is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/scripts/{name}: Update a script

  Update a script with the given name.

  **Operation ID:** `NodeScriptHandler_update`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 
  - **`{name}`** (*string*, path parameter, Required): The name of the script.

  **Request body (multipart/form-data):**

  - **`apply_configured_networking`** (*boolean*, Optional): Whether to apply the provided network configuration before the script runs.
  - **`comment`** (*string*, Optional): A comment about what this change does.
  - **`description`** (*string*, Optional): A description of what the script does.
  - **`destructive`** (*boolean*, Optional): Whether or not the script overwrites data on any drive on the running system. Destructive scripts can not be run on deployed systems. Defaults to false.
  - **`for_hardware`** (*string*, Optional): A list of modalias, PCI IDs, and/or USB IDs the script will automatically run on. Must start with `modalias:`, `pci:`, or `usb:`.
  - **`hardware_type`** (*string*, Optional): The hardware_type defines what type of hardware the script is assoicated with. May be `cpu`, `memory`, `storage`, `network`, or `node`.
  - **`may_reboot`** (*boolean*, Optional): Whether or not the script may reboot the system while running.
  - **`parallel`** (*integer*, Optional): Whether the script may be run in parallel with other scripts. May be disabled to run by itself, instance to run along scripts with the same name, or any to run along any script. `1` = True, `0` = False.
  - **`recommission`** (*boolean*, Optional): Whether built-in commissioning scripts should be rerun after successfully running this scripts.
  - **`script`** (*string*, Optional): The content of the script to be uploaded in binary form. Note: this is not a normal parameter, but a file upload. Its filename is ignored; MAAS will know it by the name you pass to the request. Optionally you can ignore the name and script parameter in favor of uploading a single file as part of the request.
  - **`tags`** (*string*, Optional): A comma seperated list of tags for this script.
  - **`timeout`** (*integer*, Optional): How long the script is allowed to run before failing. 0 gives unlimited time, defaults to 0.
  - **`title`** (*string*, Optional): The title of the script.
  - **`type`** (*string*, Optional): The type defines when the script should be used. Can be `commissioing`, `testing` or `release`. It defaults to `testing`.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the updated script.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested script is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/scripts/{name}op-add_tag: Add a tag

  Add a single tag to a script with the given name.

  **Operation ID:** `NodeScriptHandler_add_tag`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 
  - **`{name}`** (*string*, path parameter, Required): The name of the script.

  **Request body (multipart/form-data):**

  - **`tag`** (*string*, Optional): The tag being added.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the updated script.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested script is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/scripts/{name}op-download: Download a script

  Download a script with the given name.

  **Operation ID:** `NodeScriptHandler_download`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 
  - **`{name}`** (*string*, path parameter, Required): The name of the script.
  - **`revision`** (*integer*, Optional): What revision to download, latest by default. Can use rev as a shortcut.

  **Responses:**

  **HTTP 200 OK**
  
  A plain-text representation of the requested script.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested script is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/scripts/{name}op-remove_tag: Remove a tag

  Remove a tag from a script with the given name.

  **Operation ID:** `NodeScriptHandler_remove_tag`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 
  - **`{name}`** (*string*, path parameter, Required): The name of the script.

  **Request body (multipart/form-data):**

  - **`tag`** (*string*, Optional): The tag being removed.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the updated script.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested script is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/scripts/{name}op-revert: Revert a script version

  Revert a script with the given name to an earlier version.

  **Operation ID:** `NodeScriptHandler_revert`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 
  - **`{name}`** (*string*, path parameter, Required): The name of the script.

  **Request body (multipart/form-data):**

  - **`to`** (*integer*, Optional): What revision in the script's history to revert to. This can either be an ID or a negative number representing how far back to go.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the reverted script.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested script is not found.
  
  Content type: `text/plain`

````

## Node Script Result

Operations for node script result resources.

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/results/: Return script results

  Return a list of script results grouped by run for the given system_id.

  **Operation ID:** `NodeScriptResultsHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine's system_id.
  - **`type`** (*string*, Optional): Only return scripts with the given type. This can be `commissioning`, `testing`, `installion` or `release`. Defaults to showing all.
  - **`hardware_type`** (*string*, Optional): Only return scripts for the given hardware type. Can be `node`, `cpu`, `memory`, or `storage`. Defaults to all.
  - **`include_output`** (*string*, Optional): Include base64 encoded output from the script. Note that any value of include_output will include the encoded output from the script.
  - **`filters`** (*string*, Optional): A comma seperated list to show only results with a script name or tag.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of script result objects.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} DELETE /MAAS/api/2.0/nodes/{system_id}/results/{id}/: Delete script results

  Delete script results from the given system_id with the given id.
"id" can either by the script set id, `current-commissioning`, `current-testing`, or `current-installation`.

  **Operation ID:** `NodeScriptResultHandler_delete`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine's system_id.
  - **`{id}`** (*string*, path parameter, Required): The script result id.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested machine or script result is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/results/{id}/: Get specific script result

  View a set of test results for a given system_id and script id.
"id" can either by the script set id, `current-commissioning`, `current-testing`, or `current-installation`.

  **Operation ID:** `NodeScriptResultHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine's system_id.
  - **`{id}`** (*string*, path parameter, Required): The script result id.
  - **`hardware_type`** (*string*, Optional): Only return scripts for the given hardware type. Can be `node`, `cpu`, `memory`, or `storage`. Defaults to all.
  - **`include_output`** (*string*, Optional): Include the base64 encoded output from the script if any value for include_output is given.
  - **`filters`** (*string*, Optional): A comma seperated list to show only results that ran with a script name, tag, or id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested script result object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine or script result is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/nodes/{system_id}/results/{id}/: Update specific script result

  Update a set of test results for a given system_id and script id.
"id" can either be the script set id, `current-commissioning`, `current-testing`, or `current-installation`.

  **Operation ID:** `NodeScriptResultHandler_update`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine's system_id.
  - **`{id}`** (*string*, path parameter, Required): The script result id.

  **Request body (multipart/form-data):**

  - **`filters`** (*string*, Optional): A comma seperated list to show only results that ran with a script name, tag, or id.
  - **`hardware_type`** (*string*, Optional): Only return scripts for the given hardware type. Can be `node`, `cpu`, `memory`, or `storage`. Defaults to all.
  - **`include_output`** (*string*, Optional): Include the base64 encoded output from the script if any value for include_output is given.
  - **`suppressed`** (*boolean*, Optional): Set whether or not this script result should be suppressed using 'true' or 'false'.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested script result object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine or script result is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/results/{id}/op-download: Download script results

  Download a compressed tar containing all results from the given system_id with the given id.
"id" can either by the script set id, `current-commissioning`, `current-testing`, or `current-installation`.

  **Operation ID:** `NodeScriptResultHandler_download`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine's system_id.
  - **`{id}`** (*string*, path parameter, Required): The script result id.
  - **`hardware_type`** (*string*, Optional): Only return scripts for the given hardware type. Can be `node`, `cpu`, `memory`, or `storage`. Defaults to all.
  - **`filters`** (*string*, Optional): A comma seperated list to show only results that ran with a script name or tag.
  - **`output`** (*string*, Optional): Can be either `combined`, `stdout`, `stderr`, or `all`. By default only the combined output is returned.
  - **`filetype`** (*string*, Optional): Filetype to output, can be `txt` or `tar.xz`.

  **Responses:**

  **HTTP 200 OK**
  
  Plain-text output containing the requested results.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine or script result is not found.
  
  Content type: `text/plain`

````

## Node Scripts

Operations for node scripts resources.

````{dropdown} GET /MAAS/api/2.0/scripts/: List stored scripts

  Return a list of stored scripts.
Note that parameters should be passed in the URI. E.g.
`/script/?type=testing`.

  **Operation ID:** `NodeScriptsHandler_read`

  **Parameters:**

  - **`type`** (*string*, Optional): Only return scripts with the given type. This can be `commissioning`, `testing` or `release`. Defaults to showing all.
  - **`hardware_type`** (*string*, Optional): Only return scripts for the given hardware type. Can be `cpu`, `memory`, `storage`, `network`, or `node`. Defaults to all.
  - **`include_script`** (*string*, Optional): Include the base64- encoded script content.
  - **`filters`** (*string*, Optional): A comma seperated list to show only results with a script name or tag.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of script objects.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/scripts/: Create a new script

  Create a new script.

  **Operation ID:** `NodeScriptsHandler_create`

  **Request body (multipart/form-data):**

  - **`comment`** (*string*, Optional): A comment about what this change does.
  - **`description`** (*string*, Optional): A description of what the script does.
  - **`destructive`** (*boolean*, Optional): Whether or not the script overwrites data on any drive on the running system. Destructive scripts can not be run on deployed systems. Defaults to false.
  - **`for_hardware`** (*string*, Optional): A list of modalias, PCI IDs, and/or USB IDs the script will automatically run on. Must start with `modalias:`, `pci:`, or `usb:`.
  - **`hardware_type`** (*string*, Optional): The hardware_type defines what type of hardware the script is assoicated with. May be CPU, memory, storage, network, or node.
  - **`may_reboot`** (*boolean*, Optional): Whether or not the script may reboot the system while running.
  - **`name`** (*string*, Required): The name of the script.
  - **`parallel`** (*integer*, Optional): Whether the script may be run in parallel with other scripts. May be disabled to run by itself, instance to run along scripts with the same name, or any to run along any script. 1 = True, 0 = False.
  - **`recommission`** (*string*, Optional): Whether builtin commissioning scripts should be rerun after successfully running this scripts.
  - **`script`** (*string*, Optional): The content of the script to be uploaded in binary form. Note: this is not a normal parameter, but a file upload. Its filename is ignored; MAAS will know it by the name you pass to the request. Optionally you can ignore the name and script parameter in favor of uploading a single file as part of the request.
  - **`tags`** (*string*, Optional): A comma seperated list of tags for this script.
  - **`timeout`** (*integer*, Optional): How long the script is allowed to run before failing. 0 gives unlimited time, defaults to 0.
  - **`title`** (*string*, Optional): The title of the script.
  - **`type`** (*string*, Optional): The script_type defines when the script should be used: `commissioning` or `testing` or `release` or `deployment`. Defaults to `testing`.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the new script.
  
  Content type: `application/json`

````

## Nodes

Operations for nodes resources.

````{dropdown} GET /MAAS/api/2.0/nodes/: List Nodes visible to the user

  List nodes visible to current user, optionally filtered by criteria.
Nodes are sorted by id (i.e. most recent last) and grouped by type.

  **Operation ID:** `NodesHandler_read`

  **Parameters:**

  - **`hostname`** (*string*, Optional): Only nodes relating to the node with the matching hostname will be returned. This can be specified multiple times to see multiple nodes.
  - **`cpu_count`** (*integer*, Optional): Only nodes with the specified minimum number of CPUs will be included.
  - **`mem`** (*string*, Optional): Only nodes with the specified minimum amount of RAM (in MiB) will be included.
  - **`mac_address`** (*string*, Optional): Only nodes relating to the node owning the specified MAC address will be returned. This can be specified multiple times to see multiple nodes.
  - **`id`** (*string*, Optional): Only nodes relating to the nodes with matching system ids will be returned.
  - **`domain`** (*string*, Optional): Only nodes relating to the nodes in the domain will be returned.
  - **`zone`** (*string*, Optional): Only nodes relating to the nodes in the zone will be returned.
  - **`pool`** (*string*, Optional): Only nodes belonging to the pool will be returned.
  - **`agent_name`** (*string*, Optional): Only nodes relating to the nodes with matching agent names will be returned.
  - **`fabrics`** (*string*, Optional): Only nodes with interfaces in specified fabrics will be returned.
  - **`not_fabrics`** (*string*, Optional): Only nodes with interfaces not in specified fabrics will be returned.
  - **`vlans`** (*string*, Optional): Only nodes with interfaces in specified VLANs will be returned.
  - **`not_vlans`** (*string*, Optional): Only nodes with interfaces not in specified VLANs will be returned.
  - **`subnets`** (*string*, Optional): Only nodes with interfaces in specified subnets will be returned.
  - **`not_subnets`** (*string*, Optional): Only nodes with interfaces not in specified subnets will be returned.
  - **`link_speed`** (*string*, Optional): Only nodes with interfaces with link speeds greater than or equal to link_speed will be returned.
  - **`status`** (*string*, Optional): Only nodes with specified status will be returned.
  - **`pod`** (*string*, Optional): Only nodes that belong to a specified pod will be returned.
  - **`not_pod`** (*string*, Optional): Only nodes that don't belong to a specified pod will be returned.
  - **`pod_type`** (*string*, Optional): Only nodes that belong to a pod of the specified type will be returned.
  - **`not_pod_type`** (*string*, Optional): Only nodes that don't belong to a pod of the specified type will be returned.
  - **`devices`** (*string*, Optional): Only return nodes which have one or more devices containing the following constraints in the format key=value[,key2=value2[,.] Each key can be one of the following: - `vendor_id`: The device vendor id - `product_id`: The device product id - `vendor_name`: The device vendor name, not case sensative - `product_name`: The device product name, not case sensative - `commissioning_driver`: The device uses this driver during commissioning.
  - **`arch`** (*string*, Optional): Only nodes with the specified architecture will be returned.
  - **`not_arch`** (*string*, Optional): Only nodes without the specified architecture will be returned.
  - **`cpu_speed`** (*string*, Optional): Only nodes with CPUs running at the specified speed (in MHz) will be returned.
  - **`deployment_target`** (*string*, Optional): Only nodes with the specified deployment target will be returned.
  - **`not_deployment_target`** (*string*, Optional): Only nodes without the specified deployment target will be returned.
  - **`fabric_classes`** (*string*, Optional): Attached to fabric with specified classes.
  - **`not_fabric_classes`** (*string*, Optional): Not attached to fabric with specified classes.
  - **`interfaces`** (*string*, Optional): Only nodes with interfaces matching the specified constraints will be returned.
  - **`not_hostname`** (*string*, Optional): Hostnames to ignore.
  - **`not_id`** (*string*, Optional): System IDs to ignore.
  - **`not_domain`** (*string*, Optional): Domain names to ignore.
  - **`not_agent_name`** (*string*, Optional): Excludes nodes with events matching the agent name.
  - **`not_in_pool`** (*string*, Optional): Only nodes not in the specified resource pools will be returned.
  - **`not_in_zone`** (*string*, Optional): Not in zone.
  - **`not_owner`** (*string*, Optional): Only nodes not owned by the specified users will be returned.
  - **`not_power_state`** (*string*, Optional): Only nodes not in the specified power states will be returned.
  - **`not_simple_status`** (*string*, Optional): Exclude nodes with the specified simplified status.
  - **`not_status`** (*string*, Optional): Exclude nodes with the specified status.
  - **`not_tags`** (*string*, Optional): Not having tags.
  - **`owner`** (*string*, Optional): Only nodes owned by the specified users will be returned.
  - **`power_state`** (*string*, Optional): Only nodes in the specified power states will be returned.
  - **`simple_status`** (*string*, Optional): Only includes nodes with the specified simplified status.
  - **`storage`** (*string*, Optional): Only nodes with storage matching the specified constraints will be returned.
  - **`system_id`** (*string*, Optional): Only nodes with the specified system IDs will be returned.
  - **`tags`** (*string*, Optional): Only nodes with the specified tags will be returned.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of node objects.
  
  Content type: `application/json`

````

````{dropdown} GET /MAAS/api/2.0/nodes/op-is_registered: MAC address registered

  Returns whether or not the given MAC address is registered within this MAAS (and attached to a non-retired node).

  **Operation ID:** `NodesHandler_is_registered`

  **Parameters:**

  - **`mac_address`** (*object*, Required): The MAC address to be checked.

  **Responses:**

  **HTTP 200 OK**
  
  'true' or 'false'

  **HTTP 400 BAD REQUEST**
  
  mac_address was missing
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/op-set_zone: Assign nodes to a zone

  Assigns a given node to a given zone.

  **Operation ID:** `NodesHandler_set_zone`

  **Request body (multipart/form-data):**

  - **`nodes`** (*string*, Required): The node to add.
  - **`zone`** (*string*, Required): The zone name.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 400 BAD REQUEST**
  
  The given parameters were not correct.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user does not have set the zone.
  
  Content type: `text/plain`

````

## Notification

Operations for notification resources.

````{dropdown} DELETE /MAAS/api/2.0/notifications/{id}/: Delete a notification

  Delete a notification with a given id.

  **Operation ID:** `NotificationHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The notification id.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested notification is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/notifications/{id}/: Read a notification

  Read a notification with the given id.

  **Operation ID:** `NotificationHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The notification id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested notification object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested notification is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/notifications/{id}/: Update a notification

  Update a notification with a given id.
This is available to admins *only*.
Note: One of the `user`, `users` or `admins` parameters must be set to True for the notification to be visible to anyone.

  **Operation ID:** `NotificationHandler_update`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The notification id.

  **Request body (multipart/form-data):**

  - **`admins`** (*boolean*, Optional): True to notify all admins, defaults to false, i.e. not targeted to all admins.
  - **`category`** (*string*, Optional): Choose from: `error`, `warning`, `success`, or `info`. Defaults to `info`.
  - **`context`** (*string*, Optional): Optional JSON context. The root object *must* be an object (i.e. a mapping). The values herein can be referenced by `message` with Python's "format" (not %) codes.
  - **`dismissable`** (*boolean*, Optional): True to allow users dimissing the notification. Defaults to true.
  - **`ident`** (*string*, Optional): Unique identifier for this notification.
  - **`message`** (*string*, Required): The message for this notification. May contain basic HTML, such as formatting. This string will be sanitised before display so that it doesn't break MAAS HTML.
  - **`user`** (*string*, Optional): User ID this notification is intended for. By default it will not be targeted to any individual user.
  - **`users`** (*boolean*, Optional): True to notify all users, defaults to false, i.e. not targeted to all users.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated notification object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested notification is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/notifications/{id}/op-dismiss: Dismiss a notification

  Dismiss a notification with the given id.
It is safe to call multiple times for the same notification.

  **Operation ID:** `NotificationHandler_dismiss`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The notification id.

  **Responses:**

  **HTTP 200 OK**
  
  200

  **HTTP 403 FORBIDDEN**
  
  The notification is not relevant to the invoking user.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested notification is not found.
  
  Content type: `text/plain`

````

## Notifications

Operations for notifications resources.

````{dropdown} GET /MAAS/api/2.0/notifications/: List notifications

  List notifications relevant to the invoking user.
Notifications that have been dismissed are *not* returned.

  **Operation ID:** `NotificationsHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of notification objects.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/notifications/: Create a notification

  Create a new notification.
This is available to admins *only*.
Note: One of the `user`, `users` or `admins` parameters must be set to True for the notification to be visible to anyone.

  **Operation ID:** `NotificationsHandler_create`

  **Request body (multipart/form-data):**

  - **`admins`** (*boolean*, Optional): True to notify all admins, defaults to false, i.e. not targeted to all admins.
  - **`category`** (*string*, Optional): Choose from: `error`, `warning`, `success`, or `info`. Defaults to `info`.
  - **`context`** (*string*, Optional): Optional JSON context. The root object *must* be an object (i.e. a mapping). The values herein can be referenced by `message` with Python's "format" (not %) codes.
  - **`ident`** (*string*, Optional): Unique identifier for this notification.
  - **`message`** (*string*, Required): The message for this notification. May contain basic HTML, such as formatting. This string will be sanitised before display so that it doesn't break MAAS HTML.
  - **`user`** (*string*, Optional): User ID this notification is intended for. By default it will not be targeted to any individual user.
  - **`users`** (*boolean*, Optional): True to notify all users, defaults to false, i.e. not targeted to all users.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a new notification object.
  
  Content type: `application/json`

````

## OIDC provider

Operations for oidc provider resources.

````{dropdown} DELETE /MAAS/api/2.0/oidc-providers/{id}/: Delete OIDC provider

  Delete an OIDC provider by ID.

  **Operation ID:** `OidcProviderHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): ID of the OIDC provider to delete.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  404 If no OIDC provider with the specified ID exists.

````

````{dropdown} GET /MAAS/api/2.0/oidc-providers/{id}/: Get OIDC provider

  Retrieve an OIDC provider by ID.

  **Operation ID:** `OidcProviderHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): ID of the OIDC provider to retrieve.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object representing the OIDC provider.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  404 If no OIDC provider with the specified ID exists.

````

````{dropdown} PUT /MAAS/api/2.0/oidc-providers/{id}/: Update OIDC provider

  Update an existing OIDC provider by ID.

  **Operation ID:** `OidcProviderHandler_update`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): ID of the OIDC provider to update.

  **Request body (multipart/form-data):**

  - **`client_id`** (*string*, Optional): New client ID for the OIDC provider.
  - **`client_secret`** (*string*, Optional): New client secret for the OIDC provider.
  - **`enabled`** (*boolean*, Optional): Whether the OIDC provider should be enabled.
  - **`issuer_url`** (*string*, Optional): New issuer URL for the OIDC provider.
  - **`name`** (*string*, Optional): New name for the OIDC provider.
  - **`redirect_uri`** (*string*, Optional): New redirect URI for the OIDC provider.
  - **`scopes`** (*string*, Optional): Space-separated list of scopes for the OIDC provider.
  - **`token_type`** (*string*, Optional): New token type for the OIDC provider (JWT or Opaque).

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object representing the updated OIDC provider.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  404 If no OIDC provider with the specified ID exists.

````

## OIDC providers

Operations for oidc providers resources.

````{dropdown} GET /MAAS/api/2.0/oidc-providers/: List OIDC providers

  List all configured OIDC providers.

  **Operation ID:** `OidcProvidersHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of OIDC provider objects.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/oidc-providers/: Create OIDC provider

  Create a new OIDC provider.

  **Operation ID:** `OidcProvidersHandler_create`

  **Request body (multipart/form-data):**

  - **`client_id`** (*string*, Required): Client ID for the new OIDC provider.
  - **`client_secret`** (*string*, Required): Client secret for the new OIDC provider.
  - **`enabled`** (*boolean*, Optional): Whether the OIDC provider is enabled. Defaults to false.
  - **`issuer_url`** (*string*, Required): Issuer URL for the new OIDC provider.
  - **`name`** (*string*, Required): Name for the new OIDC provider.
  - **`redirect_uri`** (*string*, Optional): Redirect URI for the OIDC provider.
  - **`scopes`** (*string*, Optional): Space-separated list of scopes for the OIDC provider.
  - **`token_type`** (*string*, Optional): Token type for the OIDC provider (JWT or Opaque). Defaults to JWT.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object representing the newly created OIDC provider.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  400 If any required parameters are missing or invalid.

````

````{dropdown} GET /MAAS/api/2.0/oidc-providers/op-get_active: Get active OIDC provider

  Get the currently enabled OIDC provider.

  **Operation ID:** `OidcProvidersHandler_get_active`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object representing the active OIDC provider.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  404 If no enabled OIDC provider is found.

````

## Package Repositories

Operations for package repositories resources.

````{dropdown} GET /MAAS/api/2.0/package-repositories/: List package repositories

  List all available package repositories.

  **Operation ID:** `PackageRepositoriesHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the updated package repository.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/package-repositories/: Create a package repository

  Create a new package repository.

  **Operation ID:** `PackageRepositoriesHandler_create`

  **Request body (multipart/form-data):**

  - **`arches`** (*string*, Optional): The list of supported architectures.
  - **`components`** (*string*, Optional): The list of components to enable. Only applicable to custom repositories.
  - **`disable_sources`** (*boolean*, Optional): Disable deb-src lines.
  - **`disabled_pockets`** (*string*, Optional): The list of pockets to disable.
  - **`distributions`** (*string*, Optional): Which package distributions to include.
  - **`enabled`** (*boolean*, Optional): Whether or not the repository is enabled.
  - **`key`** (*string*, Optional): The authentication key to use with the repository.
  - **`name`** (*string*, Required): The name of the package repository.
  - **`url`** (*string*, Required): The url of the package repository.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the new package repository.
  
  Content type: `application/json`

````

## Package Repository

Operations for package repository resources.

````{dropdown} DELETE /MAAS/api/2.0/package-repositories/{id}/: Delete a package repository

  Delete a package repository with the given id.

  **Operation ID:** `PackageRepositoryHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A package repository id.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested package repository is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/package-repositories/{id}/: Read a package repository

  Read a package repository with the given id.

  **Operation ID:** `PackageRepositoryHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A package repository id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the requested package repository.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested package repository is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/package-repositories/{id}/: Update a package repository

  Update the package repository with the given id.

  **Operation ID:** `PackageRepositoryHandler_update`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A package repository id.

  **Request body (multipart/form-data):**

  - **`arches`** (*string*, Optional): The list of supported architectures.
  - **`components`** (*string*, Optional): The list of components to enable. Only applicable to custom repositories.
  - **`disable_sources`** (*boolean*, Optional): Disable deb-src lines.
  - **`disabled_components`** (*string*, Optional): The list of components to disable. Only applicable to the default Ubuntu repositories.
  - **`disabled_pockets`** (*string*, Optional): The list of pockets to disable.
  - **`distributions`** (*string*, Optional): Which package distributions to include.
  - **`enabled`** (*boolean*, Optional): Whether or not the repository is enabled.
  - **`key`** (*string*, Optional): The authentication key to use with the repository.
  - **`name`** (*string*, Optional): The name of the package repository.
  - **`url`** (*string*, Optional): The url of the package repository.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the updated package repository.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested package repository is not found.
  
  Content type: `text/plain`

````

## Partitions

Operations for partitions resources.

````{dropdown} DELETE /MAAS/api/2.0/nodes/{system_id}/blockdevices/{device_id}/partition/{id}: Delete a partition

  Delete the partition from machine system_id and device device_id with the given partition id.

  **Operation ID:** `PartitionHandler_delete`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{device_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The system_id.
  - **`{device_id}`** (*integer*, path parameter, Required): The block device_id.
  - **`{id}`** (*integer*, path parameter, Required): The partition id.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested machine, device or partition is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/blockdevices/{device_id}/partition/{id}: Read a partition

  Read the partition from machine system_id and device device_id with the given partition id.

  **Operation ID:** `PartitionHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{device_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The system_id.
  - **`{device_id}`** (*integer*, path parameter, Required): The block device_id.
  - **`{id}`** (*integer*, path parameter, Required): The partition id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested partition object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine, device or partition is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/blockdevices/{device_id}/partition/{id}op-add_tag: Add a tag

  Add a tag to a partition on machine system_id, device device_id and partition id.

  **Operation ID:** `PartitionHandler_add_tag`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{device_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The system_id.
  - **`{device_id}`** (*integer*, path parameter, Required): The block device_id.
  - **`{id}`** (*integer*, path parameter, Required): The partition id.

  **Request body (multipart/form-data):**

  - **`tag`** (*string*, Required): The tag being added.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated partition object.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permissions to add a tag.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine, device or partition is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/blockdevices/{device_id}/partition/{id}op-format: Format a partition

  Format the partition on machine system_id and device device_id with the given partition id.

  **Operation ID:** `PartitionHandler_format`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{device_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The system_id.
  - **`{device_id}`** (*integer*, path parameter, Required): The block device_id.
  - **`{id}`** (*integer*, path parameter, Required): The partition id.

  **Request body (multipart/form-data):**

  - **`fstype`** (*string*, Required): Type of filesystem.
  - **`label`** (*string*, Optional): The label for the filesystem.
  - **`uuid`** (*string*, Optional): The UUID for the filesystem.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated partition object.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permissions to format the partition.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine, device or partition is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/blockdevices/{device_id}/partition/{id}op-mount: Mount a filesystem

  Mount a filesystem on machine system_id, device device_id and partition id.

  **Operation ID:** `PartitionHandler_mount`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{device_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The system_id.
  - **`{device_id}`** (*integer*, path parameter, Required): The block device_id.
  - **`{id}`** (*integer*, path parameter, Required): The partition id.

  **Request body (multipart/form-data):**

  - **`mount_options`** (*string*, Optional): Options to pass to mount(8).
  - **`mount_point`** (*string*, Required): Path on the filesystem to mount.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated partition object.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permissions to mount the filesystem.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine, device or partition is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/blockdevices/{device_id}/partition/{id}op-remove_tag: Remove a tag

  Remove a tag from a partition on machine system_id, device device_id and partition id.

  **Operation ID:** `PartitionHandler_remove_tag`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{device_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The system_id.
  - **`{device_id}`** (*integer*, path parameter, Required): The block device_id.
  - **`{id}`** (*integer*, path parameter, Required): The partition id.

  **Request body (multipart/form-data):**

  - **`tag`** (*string*, Required): The tag being removed.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated partition object.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permissions to remove a tag.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine, device or partition is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/blockdevices/{device_id}/partition/{id}op-unformat: Unformat a partition

  Unformat the partition on machine system_id and device device_id with the given partition id.

  **Operation ID:** `PartitionHandler_unformat`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{device_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The system_id.
  - **`{device_id}`** (*integer*, path parameter, Required): The block device_id.
  - **`{id}`** (*integer*, path parameter, Required): The partition id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated partition object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine, device or partition is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/blockdevices/{device_id}/partition/{id}op-unmount: Unmount a filesystem

  Unmount a filesystem on machine system_id, device device_id and partition id.

  **Operation ID:** `PartitionHandler_unmount`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{device_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The system_id.
  - **`{device_id}`** (*integer*, path parameter, Required): The block device_id.
  - **`{id}`** (*integer*, path parameter, Required): The partition id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated partition object.
  
  Content type: `application/json`

  **HTTP 400 BAD REQUEST**
  
  The partition is not formatted or not currently mounted.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permissions to unmount the filesystem.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested machine, device or partition is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/blockdevices/{device_id}/partitions/: List partitions

  List partitions on a device with the given system_id and device_id.

  **Operation ID:** `PartitionsHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{device_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The system_id.
  - **`{device_id}`** (*integer*, path parameter, Required): The block device_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of partition objects.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine or device is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/blockdevices/{device_id}/partitions/: Create a partition

  Create a partition on a block device.

  **Operation ID:** `PartitionsHandler_create`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{device_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The system_id.
  - **`{device_id}`** (*integer*, path parameter, Required): The block device_id.

  **Request body (multipart/form-data):**

  - **`bootable`** (*boolean*, Optional): If the partition should be marked bootable.
  - **`size`** (*integer*, Optional): The size of the partition in bytes. If not specified, all available space will be used.
  - **`uuid`** (*string*, Optional): UUID for the partition. Only used if the partition table type for the block device is GPT.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new partition object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine or device is not found.
  
  Content type: `text/plain`

````

## Pod (deprecated)

Operations for pod (deprecated) resources.

````{dropdown} DELETE /MAAS/api/2.0/pods/{id}/: Deletes a VM host

  Deletes a VM host with the given ID.

  **Operation ID:** `PodHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The VM host's ID.
  - **`decompose`** (*boolean*, Optional): Whether to also also decompose all machines in the VM host on removal. If not provided, machines will not be removed.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions to delete the VM host.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  No VM host with that ID can be found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/pods/{id}/: PodHandler read

  Manage an individual Pod.
The 'Pod' endpoint has been deprecated in favour of 'vm-host'.

  **Operation ID:** `PodHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 

  **Responses:**

  **HTTP 404 NOT FOUND**
  
  'str' object has no attribute 'has_model'
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/pods/{id}/: Update a specific VM host

  Update a specific VM host by ID.
Note: A VM host's 'type' cannot be updated. The VM host must be deleted and re-added to change the type.

  **Operation ID:** `PodHandler_update`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*object*, path parameter, Required): The VM host's ID.

  **Request body (multipart/form-data):**

  - **`cpu_over_commit_ratio`** (*integer*, Optional): CPU overcommit ratio (0-10)
  - **`default_macvlan_mode`** (*string*, Optional): Default macvlan mode for VM hosts that use it: bridge, passthru, private, vepa.
  - **`default_storage_pool`** (*string*, Optional): Default KVM storage pool to use when the VM host has storage pools.
  - **`memory_over_commit_ratio`** (*integer*, Optional): CPU overcommit ratio (0-10)
  - **`name`** (*string*, Optional): The VM host's name.
  - **`pool`** (*string*, Optional): The name of the resource pool associated with this VM host - composed machines will be assigned to this resource pool by default.
  - **`power_address`** (*string*, Optional): Address for power control of the VM host.
  - **`power_pass`** (*string*, Optional): Password for access to power control of the VM host.
  - **`tags`** (*string*, Optional): Tag or tags (command separated) associated with the VM host.
  - **`zone`** (*string*, Optional): The VM host's zone.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON VM host object.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  403 - The current user does not have permission to update the VM host.

  **HTTP 404 NOT FOUND**
  
  404 - The VM host's ID was not found.

````

````{dropdown} POST /MAAS/api/2.0/pods/{id}/op-add_tag: Add a tag to a VM host

  Adds a tag to a given VM host.

  **Operation ID:** `PodHandler_add_tag`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The VM host's ID.

  **Request body (multipart/form-data):**

  - **`tag`** (*string*, Required): The tag to add.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions to delete the VM host.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  No VM host with that ID can be found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/pods/{id}/op-compose: Compose a virtual machine on the host.

  Compose a new machine from a VM host.

  **Operation ID:** `PodHandler_compose`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 

  **Request body (multipart/form-data):**

  - **`architecture`** (*string*, Optional): The architecture of the new machine (e.g. amd64). This must be an architecture the VM host supports.
  - **`cores`** (*integer*, Optional): The minimum number of CPU cores.
  - **`cpu_speed`** (*integer*, Optional): The minimum CPU speed, specified in MHz.
  - **`domain`** (*integer*, Optional): The ID of the domain in which to put the newly composed machine.
  - **`hostname`** (*string*, Optional): The hostname of the newly composed machine.
  - **`hugepages_backed`** (*boolean*, Optional): Whether to request hugepages backing for the machine.
  - **`interfaces`** (*string*, Optional): A labeled constraint map associating constraint labels with desired interface properties. MAAS will assign interfaces that match the given interface properties. Format: `label:key=value,key=value,.` Keys: - `id`: Matches an interface with the specific id - `fabric`: Matches an interface attached to the specified fabric. - `fabric_class`: Matches an interface attached to a fabric with the specified class. - `ip`: Matches an interface whose VLAN is on the subnet implied by the given IP address, and allocates the specified IP address for the machine on that interface (if it is available). - `mode`: Matches an interface with the specified mode. (Currently, the only supported mode is "unconfigured".) - `name`: Matches an interface with the specified name. (For example, "eth0".) - `hostname`: Matches an interface attached to the node with the specified hostname. - `subnet`: Matches an interface attached to the specified subnet. - `space`: Matches an interface attached to the specified space. - `subnet_cidr`: Matches an interface attached to the specified subnet CIDR. (For example, "192.168.0.0/24".) - `type`: Matches an interface of the specified type. (Valid types: "physical", "vlan", "bond", "bridge", or "unknown".) - `vlan`: Matches an interface on the specified VLAN. - `vid`: Matches an interface on a VLAN with the specified VID. - `tag`: Matches an interface tagged with the specified tag.
  - **`memory`** (*integer*, Optional): The minimum amount of memory, specified in MiB (e.g. 2 MiB = 2*1024*1024).
  - **`pinned_cores`** (*integer*, Optional): List of host CPU cores to pin the VM to. If this is passed, the "cores" parameter is ignored.
  - **`pool`** (*integer*, Optional): The ID of the pool in which to put the newly composed machine.
  - **`storage`** (*string*, Optional): A list of storage constraint identifiers in the form `label:size(tag,tag,.), label:size(tag,tag,.)`. For more information please see the CLI VM host management page of the official MAAS documentation.
  - **`zone`** (*integer*, Optional): The ID of the zone in which to put the newly composed machine.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new machine ID and resource URI.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions to delete the VM host.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  No VM host with that ID can be found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/pods/{id}/op-parameters: Obtain VM host parameters

  This returns a VM host's configuration parameters. For some types of VM host, this will include private information such as passwords and secret keys.
Note: This method is reserved for admin users.

  **Operation ID:** `PodHandler_parameters`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The VM host's ID.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the VM host's configuration parameters.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions to delete the VM host.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  No VM host with that ID can be found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/pods/{id}/op-refresh: Refresh a VM host

  Performs VM host discovery and updates all discovered information and discovered machines.

  **Operation ID:** `PodHandler_refresh`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The VM host's ID.

  **Responses:**

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions to delete the VM host.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  No VM host with that ID can be found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/pods/{id}/op-remove_tag: Remove a tag from a VM host

  Removes a given tag from a VM host.

  **Operation ID:** `PodHandler_remove_tag`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The VM host's ID.

  **Request body (multipart/form-data):**

  - **`tag`** (*string*, Required): The tag to add.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions to delete the VM host.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  No VM host with that ID can be found.
  
  Content type: `text/plain`

````

## Pods (deprecated)

Operations for pods (deprecated) resources.

````{dropdown} GET /MAAS/api/2.0/pods/: List VM hosts

  Get a listing of all VM hosts.

  **Operation ID:** `PodsHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of VM host objects.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/pods/: Create a VM host

  Create or discover a new VM host.

  **Operation ID:** `PodsHandler_create`

  **Request body (multipart/form-data):**

  - **`certificate`** (*string*, Optional): X.509 certificate used to verify the identity of the user. If `certificate` and `key` are not provided, and the VM created is LXD type, a X.509 certificate will be created.
  - **`key`** (*string*, Optional): private key used for authentication. If `certificate` and `key` are not provided, and the VM created is LXD type, a RSA key will be created.
  - **`name`** (*string*, Optional): The new VM host's name.
  - **`pool`** (*string*, Optional): The name of the resource pool the new VM host will belong to. Machines composed from this VM host will be assigned to this resource pool by default.
  - **`power_address`** (*string*, Required): Address that gives MAAS access to the VM host power control. For example, for virsh `qemu+ssh:/172.16.99.2/system` For `lxd`, this is just the address of the host.
  - **`power_pass`** (*string*, Required): Password to use for power control of the VM host. Required `virsh` VM hosts that do not have SSH set up for public-key authentication and for `lxd` if the MAAS certificate is not registered already in the LXD server.
  - **`power_user`** (*string*, Required): Username to use for power control of the VM host. Required for `virsh` VM hosts that do not have SSH set up for public-key authentication.
  - **`project`** (*string*, Optional): For `lxd` VM hosts, the project that MAAS will manage. If not provided, the `default` project will be used. If a nonexistent name is given, a new project with that name will be created.
  - **`tags`** (*string*, Optional): A tag or list of tags ( comma delimited) to assign to the new VM host.
  - **`type`** (*string*, Required): The type of VM host to create: `lxd` or `virsh`.
  - **`zone`** (*string*, Optional): The new VM host's zone.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a VM host object.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions to delete the VM host.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  No VM host with that ID can be found.
  
  Content type: `text/plain`

  **HTTP 503 SERVICE UNAVAILABLE**
  
  MAAS could not find or could not authenticate with the VM host.
  
  Content type: `text/plain`

````

## RAID Device

Operations for raid device resources.

````{dropdown} DELETE /MAAS/api/2.0/nodes/{system_id}/raid/{id}/: Delete a RAID

  Delete a RAID with the given id on a machine with the given system_id.

  **Operation ID:** `RaidHandler_delete`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The system_id of the machine containing the RAID.
  - **`{id}`** (*integer*, path parameter, Required): A RAID id.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested machine or RAID is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/raid/{id}/: Read a RAID

  Read RAID with the given id on a machine with the given system_id.

  **Operation ID:** `RaidHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The system_id of the machine containing the RAID.
  - **`{id}`** (*integer*, path parameter, Required): A RAID id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested RAID.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine or RAID is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/nodes/{system_id}/raid/{id}/: Update a RAID

  Update a RAID with the given id on a machine with the given system_id.

  **Operation ID:** `RaidHandler_update`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The system_id of the machine containing the RAID.
  - **`{id}`** (*integer*, path parameter, Required): A RAID id.

  **Request body (multipart/form-data):**

  - **`add_block_devices`** (*string*, Optional): Block devices to add to the RAID.
  - **`add_partitions`** (*string*, Optional): Partitions to add to the RAID.
  - **`add_spare_devices`** (*string*, Optional): Spare block devices to add to the RAID.
  - **`add_spare_partitions`** (*string*, Optional): Spare partitions to add to the RAID.
  - **`name`** (*string*, Optional): Name of the RAID.
  - **`remove_block_devices`** (*string*, Optional): Block devices to remove from the RAID.
  - **`remove_partitions`** (*string*, Optional): Partitions to remove from the RAID.
  - **`remove_spare_devices`** (*string*, Optional): Spare block devices to remove from the RAID.
  - **`remove_spare_partitions`** (*string*, Optional): Spare partitions to remove from the RAID.
  - **`uuid`** (*string*, Optional): UUID of the RAID.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated RAID.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine or RAID id is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

## RAID Devices

Operations for raid devices resources.

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/raids/: List all RAIDs

  List all RAIDs belonging to a machine with the given system_id.

  **Operation ID:** `RaidsHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The system_id of the machine containing the RAIDs.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of available RAIDs.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/raids/: Set up a RAID

  Set up a RAID on a machine with the given system_id.

  **Operation ID:** `RaidsHandler_create`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The system_id of the machine on which to set up the RAID.

  **Request body (multipart/form-data):**

  - **`block_devices`** (*string*, Optional): Block devices to add to the RAID.
  - **`level`** (*integer*, Required): RAID level.
  - **`name`** (*string*, Optional): Name of the RAID.
  - **`partitions`** (*string*, Optional): Partitions to add to the RAID.
  - **`spare_devices`** (*string*, Optional): Spare block devices to add to the RAID.
  - **`spare_partitions`** (*string*, Optional): Spare partitions to add to the RAID.
  - **`uuid`** (*string*, Optional): UUID of the RAID.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the new RAID.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

## RackController

Operations for rackcontroller resources.

````{dropdown} DELETE /MAAS/api/2.0/rackcontrollers/{system_id}/: Delete a rack controller

  Deletes a rack controller with the given system_id. A rack controller cannot be deleted if it is set to `primary_rack` on a `VLAN` and another rack controller cannot be used to provide DHCP for said VLAN. Use `force` to override this behavior.
Using `force` will also allow deleting a rack controller that is hosting pod virtual machines. The pod will also be deleted.
Rack controllers that are also region controllers will be converted to a region controller (and hosted pods will not be affected).

  **Operation ID:** `RackControllerHandler_delete`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`force`** (*boolean*, Optional): Always delete the rack controller even if it is the `primary_rack` on a `VLAN` and another rack controller cannot provide DHCP on that VLAN. This will disable DHCP on those VLANs.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 400 BAD REQUEST**
  
  Unable to delete 'maas-run'; it is currently set as a primary rack controller on VLANs fabric-0.untagged and no other rack controller can provide DHCP.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permssions to delete the rack controller.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested rack controller system_id is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/rackcontrollers/{system_id}/: Read a node

  Reads a node with the given system_id.

  **Operation ID:** `RackControllerHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A node's system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the requested node.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/rackcontrollers/{system_id}/: Update a rack controller

  Updates a rack controller with the given system_id.

  **Operation ID:** `RackControllerHandler_update`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 

  **Request body (multipart/form-data):**

  - **`description`** (*string*, Optional): The new description for this given rack controller.
  - **`domain`** (*string*, Optional): The domain for this controller. If not given the default domain is used.
  - **`power_parameters_skip_check`** (*boolean*, Optional): If true, the new power parameters for the given rack controller will be checked against the expected parameters for the rack controller's power type. Default is false.
  - **`power_parameters_{param}`** (*string*, Required): The new value for the 'param' power parameter. This is a dynamic parameter that depends on the rack controller's power_type. See the `Power types`_ section for a list of available parameters based on power type. Note that only admin users can set these parameters.
  - **`power_type`** (*string*, Optional): The new power type for the given rack controller. If you use the default value, power_parameters will be set to an empty string. See the `Power types`_ section for a list of available power types. Note that only admin users can set this parameter.
  - **`zone`** (*string*, Optional): The name of a valid zone in which to place the given rack controller.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated rack-controller object.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  This method is reserved for admin users.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested rack controller system_id is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/rackcontrollers/{system_id}/op-abort: Abort a node operation

  Abort a node's current operation.

  **Operation ID:** `RackControllerHandler_abort`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 

  **Request body (multipart/form-data):**

  - **`comment`** (*string*, Optional): Comment for the event log.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The user is not authorized to abort the current operation.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/rackcontrollers/{system_id}/op-details: Get system details

  Returns system details - for example, LLDP and `lshw` XML dumps.
Returns a `{detail_type: xml, .}` map, where `detail_type` is something like "lldp" or "lshw".
Note that this is returned as BSON and not JSON. This is for efficiency, but mainly because JSON can't do binary content without applying additional encoding like base-64. The example output below is represented in ASCII using `bsondump example.bson` and is for demonstrative purposes.

  **Operation ID:** `RackControllerHandler_details`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The node's system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A BSON object represented here in ASCII using `bsondump example.bson`.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to see the node details.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} ~~POST /MAAS/api/2.0/rackcontrollers/{system_id}/op-import_boot_images: Import boot images~~

  Import boot images on a given rack controller or all rack controllers. (deprecated)

  ```{warning}
  This endpoint is deprecated.
  ```

  **Operation ID:** `RackControllerHandler_import_boot_images`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A rack controller system_id.

  **Responses:**

  **HTTP 202 ACCEPTED**
  
  No action
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested rack controller system_id is not found.
  
  Content type: `text/plain`

````

````{dropdown} ~~GET /MAAS/api/2.0/rackcontrollers/{system_id}/op-list_boot_images: List available boot images~~

  Lists all available boot images for a given rack controller system_id and whether they are in sync with the region controller. (deprecated)

  ```{warning}
  This endpoint is deprecated.
  ```

  **Operation ID:** `RackControllerHandler_list_boot_images`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The rack controller system_id for which you want to list boot images.

  **Responses:**

  **HTTP 404 NOT FOUND**
  
  The requested rack controller system_id is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/rackcontrollers/{system_id}/op-override_failed_testing: Ignore failed tests

  Ignore failed tests and put node back into a usable state.

  **Operation ID:** `RackControllerHandler_override_failed_testing`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 

  **Request body (multipart/form-data):**

  - **`comment`** (*string*, Optional): Comment for the event log.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The user is not authorized to override tests.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/rackcontrollers/{system_id}/op-power_off: Power off a node

  Powers off a given node.

  **Operation ID:** `RackControllerHandler_power_off`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 

  **Request body (multipart/form-data):**

  - **`comment`** (*string*, Optional): Comment for the event log.
  - **`stop_mode`** (*string*, Optional): Power-off mode. If 'soft', perform a soft power down if the node's power type supports it, otherwise perform a hard power off. For all values other than 'soft', and by default, perform a hard power off. A soft power off generally asks the OS to shutdown the system gracefully before powering off, while a hard power off occurs immediately without any warning to the OS.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  A JSON object containing the node's information.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user is not authorized to power off the node.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/rackcontrollers/{system_id}/op-power_on: Turn on a node

  Turn on the given node with optional user-data and comment.

  **Operation ID:** `RackControllerHandler_power_on`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 

  **Request body (multipart/form-data):**

  - **`comment`** (*string*, Optional): Comment for the event log.
  - **`user_data`** (*string*, Optional): Base64-encoded blob of data to be made available to the nodes through the metadata service.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  A JSON object containing the node's information.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user is not authorized to power on the node.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

  **HTTP 503 SERVICE UNAVAILABLE**
  
  Returns 503 if the start-up attempted to allocate an IP address, and there were no IP addresses available on the relevant cluster interface.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/rackcontrollers/{system_id}/op-power_parameters: Get power parameters

  Gets power parameters for a given system_id, if any. For some types of power control this will include private information such as passwords and secret keys.
Note that this method is reserved for admin users and returns a 403 if the user is not one.

  **Operation ID:** `RackControllerHandler_power_parameters`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 

  **Responses:**

  **HTTP 200 OK**
  
  200

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to see the power parameters.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/rackcontrollers/{system_id}/op-query_power_state: Get the power state of a node

  Gets the power state of a given node. MAAS sends a request to the node's power controller, which asks it about the node's state.
The reply to this could be delayed by up to 30 seconds while waiting for the power controller to respond.  Use this method sparingly as it ties up an appserver thread while waiting.

  **Operation ID:** `RackControllerHandler_query_power_state`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The node to query.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the node's power state.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/rackcontrollers/{system_id}/op-test: Begin testing process for a node

  Begins the testing process for a given node.
A node in the 'ready', 'allocated', 'deployed', 'broken', or any failed state may run tests. If testing is started and successfully passes from 'broken' or any failed state besides 'failed commissioning' the node will be returned to a ready state. Otherwise the node will return to the state it was when testing started.

  **Operation ID:** `RackControllerHandler_test`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 

  **Request body (multipart/form-data):**

  - **`enable_ssh`** (*integer*, Optional): Whether to enable SSH for the testing environment using the user's SSH key(s). 0 = false. 1 = true.
  - **`parameters`** (*string*, Optional): Scripts selected to run may define their own parameters. These parameters may be passed using the parameter name. Optionally a parameter may have the script name prepended to have that parameter only apply to that specific script.
  - **`testing_scripts`** (*string*, Optional): A comma-separated list of testing script names and tags to be run. By default all tests tagged 'commissioning' will be run.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  A JSON object containing the node's information.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

## RackControllers

Operations for rackcontrollers resources.

````{dropdown} GET /MAAS/api/2.0/rackcontrollers/: List Nodes visible to the user

  List nodes visible to current user, optionally filtered by criteria.
Nodes are sorted by id (i.e. most recent last) and grouped by type.

  **Operation ID:** `RackControllersHandler_read`

  **Parameters:**

  - **`hostname`** (*string*, Optional): Only nodes relating to the node with the matching hostname will be returned. This can be specified multiple times to see multiple nodes.
  - **`cpu_count`** (*integer*, Optional): Only nodes with the specified minimum number of CPUs will be included.
  - **`mem`** (*string*, Optional): Only nodes with the specified minimum amount of RAM (in MiB) will be included.
  - **`mac_address`** (*string*, Optional): Only nodes relating to the node owning the specified MAC address will be returned. This can be specified multiple times to see multiple nodes.
  - **`id`** (*string*, Optional): Only nodes relating to the nodes with matching system ids will be returned.
  - **`domain`** (*string*, Optional): Only nodes relating to the nodes in the domain will be returned.
  - **`zone`** (*string*, Optional): Only nodes relating to the nodes in the zone will be returned.
  - **`pool`** (*string*, Optional): Only nodes belonging to the pool will be returned.
  - **`agent_name`** (*string*, Optional): Only nodes relating to the nodes with matching agent names will be returned.
  - **`fabrics`** (*string*, Optional): Only nodes with interfaces in specified fabrics will be returned.
  - **`not_fabrics`** (*string*, Optional): Only nodes with interfaces not in specified fabrics will be returned.
  - **`vlans`** (*string*, Optional): Only nodes with interfaces in specified VLANs will be returned.
  - **`not_vlans`** (*string*, Optional): Only nodes with interfaces not in specified VLANs will be returned.
  - **`subnets`** (*string*, Optional): Only nodes with interfaces in specified subnets will be returned.
  - **`not_subnets`** (*string*, Optional): Only nodes with interfaces not in specified subnets will be returned.
  - **`link_speed`** (*string*, Optional): Only nodes with interfaces with link speeds greater than or equal to link_speed will be returned.
  - **`status`** (*string*, Optional): Only nodes with specified status will be returned.
  - **`pod`** (*string*, Optional): Only nodes that belong to a specified pod will be returned.
  - **`not_pod`** (*string*, Optional): Only nodes that don't belong to a specified pod will be returned.
  - **`pod_type`** (*string*, Optional): Only nodes that belong to a pod of the specified type will be returned.
  - **`not_pod_type`** (*string*, Optional): Only nodes that don't belong to a pod of the specified type will be returned.
  - **`devices`** (*string*, Optional): Only return nodes which have one or more devices containing the following constraints in the format key=value[,key2=value2[,.] Each key can be one of the following: - `vendor_id`: The device vendor id - `product_id`: The device product id - `vendor_name`: The device vendor name, not case sensative - `product_name`: The device product name, not case sensative - `commissioning_driver`: The device uses this driver during commissioning.
  - **`arch`** (*string*, Optional): Only nodes with the specified architecture will be returned.
  - **`not_arch`** (*string*, Optional): Only nodes without the specified architecture will be returned.
  - **`cpu_speed`** (*string*, Optional): Only nodes with CPUs running at the specified speed (in MHz) will be returned.
  - **`deployment_target`** (*string*, Optional): Only nodes with the specified deployment target will be returned.
  - **`not_deployment_target`** (*string*, Optional): Only nodes without the specified deployment target will be returned.
  - **`fabric_classes`** (*string*, Optional): Attached to fabric with specified classes.
  - **`not_fabric_classes`** (*string*, Optional): Not attached to fabric with specified classes.
  - **`interfaces`** (*string*, Optional): Only nodes with interfaces matching the specified constraints will be returned.
  - **`not_hostname`** (*string*, Optional): Hostnames to ignore.
  - **`not_id`** (*string*, Optional): System IDs to ignore.
  - **`not_domain`** (*string*, Optional): Domain names to ignore.
  - **`not_agent_name`** (*string*, Optional): Excludes nodes with events matching the agent name.
  - **`not_in_pool`** (*string*, Optional): Only nodes not in the specified resource pools will be returned.
  - **`not_in_zone`** (*string*, Optional): Not in zone.
  - **`not_owner`** (*string*, Optional): Only nodes not owned by the specified users will be returned.
  - **`not_power_state`** (*string*, Optional): Only nodes not in the specified power states will be returned.
  - **`not_simple_status`** (*string*, Optional): Exclude nodes with the specified simplified status.
  - **`not_status`** (*string*, Optional): Exclude nodes with the specified status.
  - **`not_tags`** (*string*, Optional): Not having tags.
  - **`owner`** (*string*, Optional): Only nodes owned by the specified users will be returned.
  - **`power_state`** (*string*, Optional): Only nodes in the specified power states will be returned.
  - **`simple_status`** (*string*, Optional): Only includes nodes with the specified simplified status.
  - **`storage`** (*string*, Optional): Only nodes with storage matching the specified constraints will be returned.
  - **`system_id`** (*string*, Optional): Only nodes with the specified system IDs will be returned.
  - **`tags`** (*string*, Optional): Only nodes with the specified tags will be returned.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of node objects.
  
  Content type: `application/json`

````

````{dropdown} GET /MAAS/api/2.0/rackcontrollers/op-describe_power_types: Get power information from rack controllers

  Queries all rack controllers for power information.

  **Operation ID:** `RackControllersHandler_describe_power_types`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a dictionary with system_ids as keys and power parameters as values.
  
  Content type: `application/json`

````

````{dropdown} ~~POST /MAAS/api/2.0/rackcontrollers/op-import_boot_images: Import boot images on all rack controllers~~

  Imports boot images on all rack controllers. (deprecated)

  ```{warning}
  This endpoint is deprecated.
  ```

  **Operation ID:** `RackControllersHandler_import_boot_images`

  **Responses:**

  **HTTP 202 ACCEPTED**
  
  No action
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/rackcontrollers/op-is_registered: MAC address registered

  Returns whether or not the given MAC address is registered within this MAAS (and attached to a non-retired node).

  **Operation ID:** `RackControllersHandler_is_registered`

  **Parameters:**

  - **`mac_address`** (*object*, Required): The MAC address to be checked.

  **Responses:**

  **HTTP 200 OK**
  
  'true' or 'false'

  **HTTP 400 BAD REQUEST**
  
  mac_address was missing
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/rackcontrollers/op-power_parameters: Get power parameters

  Get power parameters for multiple machines. To request power parameters for a specific machine or more than one machine:
`op=power_parameters&id=abc123&id=def456`.

  **Operation ID:** `RackControllersHandler_power_parameters`

  **Parameters:**

  - **`id`** (*object*, Required): A system ID. To request more than one machine, provide multiple `id` arguments in the request. Only machines with matching system ids will be returned.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of power parameters with system_ids as keys.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user is not authorized to view the power parameters.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/rackcontrollers/op-set_zone: Assign nodes to a zone

  Assigns a given node to a given zone.

  **Operation ID:** `RackControllersHandler_set_zone`

  **Request body (multipart/form-data):**

  - **`nodes`** (*string*, Required): The node to add.
  - **`zone`** (*string*, Required): The zone name.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 400 BAD REQUEST**
  
  The given parameters were not correct.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user does not have set the zone.
  
  Content type: `text/plain`

````

## RegionController

Operations for regioncontroller resources.

````{dropdown} DELETE /MAAS/api/2.0/regioncontrollers/{system_id}/: Delete a region controller

  Deletes a region controller with the given system_id.
A region controller cannot be deleted if it hosts pod virtual machines.
Use `force` to override this behavior. Forcing deletion will also remove hosted pods.

  **Operation ID:** `RegionControllerHandler_delete`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The region controller's system_id.
  - **`force`** (*boolean*, Optional): Tells MAAS to override disallowing deletion of region controllers that host pod virtual machines.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 400 BAD REQUEST**
  
  If MAAS is unable to delete the region controller.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to delete the rack controller.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested rack controller system_id is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/regioncontrollers/{system_id}/: Read a node

  Reads a node with the given system_id.

  **Operation ID:** `RegionControllerHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): A node's system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the requested node.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/regioncontrollers/{system_id}/: Update a region controller

  Updates a region controller with the given system_id.

  **Operation ID:** `RegionControllerHandler_update`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The region controller's system_id.

  **Request body (multipart/form-data):**

  - **`description`** (*string*, Optional): The new description for this given region controller.
  - **`power_parameters_skip_check`** (*boolean*, Optional): Whether or not the new power parameters for this region controller should be checked against the expected power parameters for the region controller's power type ('true' or 'false'). The default is 'false'.
  - **`power_parameters_{param1}`** (*string*, Required): The new value for the 'param1' power parameter. Note that this is dynamic as the available parameters depend on the selected value of the region controller's power_type. Available to admin users. See the `Power types`_ section for a list of the available power parameters for each power type.
  - **`power_type`** (*string*, Optional): The new power type for this region controller. If you use the default value, power_parameters will be set to the empty string. Available to admin users. See the `Power types`_ section for a list of the available power types.
  - **`zone`** (*string*, Optional): Name of a valid physical zone in which to place this region controller.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the updated region controller object.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to update the region controller.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested region controller system_id is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/regioncontrollers/{system_id}/op-details: Get system details

  Returns system details - for example, LLDP and `lshw` XML dumps.
Returns a `{detail_type: xml, .}` map, where `detail_type` is something like "lldp" or "lshw".
Note that this is returned as BSON and not JSON. This is for efficiency, but mainly because JSON can't do binary content without applying additional encoding like base-64. The example output below is represented in ASCII using `bsondump example.bson` and is for demonstrative purposes.

  **Operation ID:** `RegionControllerHandler_details`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The node's system_id.

  **Responses:**

  **HTTP 200 OK**
  
  A BSON object represented here in ASCII using `bsondump example.bson`.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to see the node details.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/regioncontrollers/{system_id}/op-power_parameters: Get power parameters

  Gets power parameters for a given system_id, if any. For some types of power control this will include private information such as passwords and secret keys.
Note that this method is reserved for admin users and returns a 403 if the user is not one.

  **Operation ID:** `RegionControllerHandler_power_parameters`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 

  **Responses:**

  **HTTP 200 OK**
  
  200

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to see the power parameters.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested node is not found.
  
  Content type: `text/plain`

````

## RegionControllers

Operations for regioncontrollers resources.

````{dropdown} GET /MAAS/api/2.0/regioncontrollers/: List Nodes visible to the user

  List nodes visible to current user, optionally filtered by criteria.
Nodes are sorted by id (i.e. most recent last) and grouped by type.

  **Operation ID:** `RegionControllersHandler_read`

  **Parameters:**

  - **`hostname`** (*string*, Optional): Only nodes relating to the node with the matching hostname will be returned. This can be specified multiple times to see multiple nodes.
  - **`cpu_count`** (*integer*, Optional): Only nodes with the specified minimum number of CPUs will be included.
  - **`mem`** (*string*, Optional): Only nodes with the specified minimum amount of RAM (in MiB) will be included.
  - **`mac_address`** (*string*, Optional): Only nodes relating to the node owning the specified MAC address will be returned. This can be specified multiple times to see multiple nodes.
  - **`id`** (*string*, Optional): Only nodes relating to the nodes with matching system ids will be returned.
  - **`domain`** (*string*, Optional): Only nodes relating to the nodes in the domain will be returned.
  - **`zone`** (*string*, Optional): Only nodes relating to the nodes in the zone will be returned.
  - **`pool`** (*string*, Optional): Only nodes belonging to the pool will be returned.
  - **`agent_name`** (*string*, Optional): Only nodes relating to the nodes with matching agent names will be returned.
  - **`fabrics`** (*string*, Optional): Only nodes with interfaces in specified fabrics will be returned.
  - **`not_fabrics`** (*string*, Optional): Only nodes with interfaces not in specified fabrics will be returned.
  - **`vlans`** (*string*, Optional): Only nodes with interfaces in specified VLANs will be returned.
  - **`not_vlans`** (*string*, Optional): Only nodes with interfaces not in specified VLANs will be returned.
  - **`subnets`** (*string*, Optional): Only nodes with interfaces in specified subnets will be returned.
  - **`not_subnets`** (*string*, Optional): Only nodes with interfaces not in specified subnets will be returned.
  - **`link_speed`** (*string*, Optional): Only nodes with interfaces with link speeds greater than or equal to link_speed will be returned.
  - **`status`** (*string*, Optional): Only nodes with specified status will be returned.
  - **`pod`** (*string*, Optional): Only nodes that belong to a specified pod will be returned.
  - **`not_pod`** (*string*, Optional): Only nodes that don't belong to a specified pod will be returned.
  - **`pod_type`** (*string*, Optional): Only nodes that belong to a pod of the specified type will be returned.
  - **`not_pod_type`** (*string*, Optional): Only nodes that don't belong to a pod of the specified type will be returned.
  - **`devices`** (*string*, Optional): Only return nodes which have one or more devices containing the following constraints in the format key=value[,key2=value2[,.] Each key can be one of the following: - `vendor_id`: The device vendor id - `product_id`: The device product id - `vendor_name`: The device vendor name, not case sensative - `product_name`: The device product name, not case sensative - `commissioning_driver`: The device uses this driver during commissioning.
  - **`arch`** (*string*, Optional): Only nodes with the specified architecture will be returned.
  - **`not_arch`** (*string*, Optional): Only nodes without the specified architecture will be returned.
  - **`cpu_speed`** (*string*, Optional): Only nodes with CPUs running at the specified speed (in MHz) will be returned.
  - **`deployment_target`** (*string*, Optional): Only nodes with the specified deployment target will be returned.
  - **`not_deployment_target`** (*string*, Optional): Only nodes without the specified deployment target will be returned.
  - **`fabric_classes`** (*string*, Optional): Attached to fabric with specified classes.
  - **`not_fabric_classes`** (*string*, Optional): Not attached to fabric with specified classes.
  - **`interfaces`** (*string*, Optional): Only nodes with interfaces matching the specified constraints will be returned.
  - **`not_hostname`** (*string*, Optional): Hostnames to ignore.
  - **`not_id`** (*string*, Optional): System IDs to ignore.
  - **`not_domain`** (*string*, Optional): Domain names to ignore.
  - **`not_agent_name`** (*string*, Optional): Excludes nodes with events matching the agent name.
  - **`not_in_pool`** (*string*, Optional): Only nodes not in the specified resource pools will be returned.
  - **`not_in_zone`** (*string*, Optional): Not in zone.
  - **`not_owner`** (*string*, Optional): Only nodes not owned by the specified users will be returned.
  - **`not_power_state`** (*string*, Optional): Only nodes not in the specified power states will be returned.
  - **`not_simple_status`** (*string*, Optional): Exclude nodes with the specified simplified status.
  - **`not_status`** (*string*, Optional): Exclude nodes with the specified status.
  - **`not_tags`** (*string*, Optional): Not having tags.
  - **`owner`** (*string*, Optional): Only nodes owned by the specified users will be returned.
  - **`power_state`** (*string*, Optional): Only nodes in the specified power states will be returned.
  - **`simple_status`** (*string*, Optional): Only includes nodes with the specified simplified status.
  - **`storage`** (*string*, Optional): Only nodes with storage matching the specified constraints will be returned.
  - **`system_id`** (*string*, Optional): Only nodes with the specified system IDs will be returned.
  - **`tags`** (*string*, Optional): Only nodes with the specified tags will be returned.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of node objects.
  
  Content type: `application/json`

````

````{dropdown} GET /MAAS/api/2.0/regioncontrollers/op-is_registered: MAC address registered

  Returns whether or not the given MAC address is registered within this MAAS (and attached to a non-retired node).

  **Operation ID:** `RegionControllersHandler_is_registered`

  **Parameters:**

  - **`mac_address`** (*object*, Required): The MAC address to be checked.

  **Responses:**

  **HTTP 200 OK**
  
  'true' or 'false'

  **HTTP 400 BAD REQUEST**
  
  mac_address was missing
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/regioncontrollers/op-set_zone: Assign nodes to a zone

  Assigns a given node to a given zone.

  **Operation ID:** `RegionControllersHandler_set_zone`

  **Request body (multipart/form-data):**

  - **`nodes`** (*string*, Required): The node to add.
  - **`zone`** (*string*, Required): The zone name.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 400 BAD REQUEST**
  
  The given parameters were not correct.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user does not have set the zone.
  
  Content type: `text/plain`

````

## Reserved IP

Operations for reserved ip resources.

````{dropdown} DELETE /MAAS/api/2.0/reservedips/{id}/: Delete a reserved IP

  Delete a reserved IP given its ID.

  **Operation ID:** `ReservedIpHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The ID of the Reserved IP to be deleted.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to delete the reserved IP.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested reserved IP is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/reservedips/{id}/: Read a Reserved IP

  Read a reserved IP given its ID.

  **Operation ID:** `ReservedIpHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of reserved IPs.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested reserved IP is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/reservedips/{id}/: Update a reserved IP

  Update a reserved IP given its ID.

  **Operation ID:** `ReservedIpHandler_update`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The ID of the Reserved IP to be updated.

  **Request body (multipart/form-data):**

  - **`comment`** (*string*, Optional): A description of this reserved IP.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested reserved IP.
  
  Content type: `application/json`

  **HTTP 400 BAD REQUEST**
  
  IP is updated to a value belonging to another subnet. IP is updated to an IP already reserved.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to update the reserved IP.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested reserved IP range is not found.
  
  Content type: `text/plain`

````

## Reserved IPs

Operations for reserved ips resources.

````{dropdown} GET /MAAS/api/2.0/reservedips/: List all available Reserved IPs

  List all IPs that have been reserved in MAAS.

  **Operation ID:** `ReservedIpsHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of reserved IPs.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/reservedips/: Create a Reserved IP

  Create a new Reserved IP.

  **Operation ID:** `ReservedIpsHandler_create`

  **Request body (multipart/form-data):**

  - **`comment`** (*string*, Optional): A description of this reserved IP.
  - **`ip`** (*string*, Required): The IP to be reserved.
  - **`mac_address`** (*string*, Optional): The MAC address that should be linked to the reserved IP.
  - **`subnet`** (*integer*, Optional): ID of the subnet associated with the IP to be reserved.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the reserved IP.
  
  Content type: `application/json`

  **HTTP 400 BAD REQUEST**
  
  IP parameter is required, and cannot be null or reserved. MAC address and VLAN need to be a unique together. IP needs to be within the subnet range. Subnet and VLAN for the reserved IP needs to be defined in MAAS.
  
  Content type: `text/plain`

  **HTTP 403 FORBIDDEN**
  
  The user does not have permission to create the reserved IP.
  
  Content type: `text/plain`

````

## Resource pool

Operations for resource pool resources.

````{dropdown} DELETE /MAAS/api/2.0/resourcepool/{id}/: ResourcePoolHandler delete

  Deletes a resource pool.

  **Operation ID:** `ResourcePoolHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*object*, path parameter, Required): The resource pool name/id to delete.

  **Responses:**

  **HTTP 200 OK**
  
  An empty string
  
  Content type: `text/plain`

  **HTTP 204 NO CONTENT**
  
  An empty string
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/resourcepool/{id}/: ResourcePoolHandler read

  Returns a resource pool.

  **Operation ID:** `ResourcePoolHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*object*, path parameter, Required): A resource pool id/name.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing resource pool information
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The resource pool name is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/resourcepool/{id}/: ResourcePoolHandler update

  Updates a resource pool's name or description.
Note that any other given parameters are silently ignored.

  **Operation ID:** `ResourcePoolHandler_update`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*object*, path parameter, Required): The resource pool id/name to update.

  **Request body (multipart/form-data):**

  - **`description`** (*string*, Optional): A brief description of the resource pool.
  - **`name`** (*string*, Optional): The resource pool's new name.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing details about your new resource pool.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  Zone not found
  
  Content type: `text/plain`

````

## Resource pools

Operations for resource pools resources.

````{dropdown} GET /MAAS/api/2.0/resourcepools/: ResourcePoolsHandler read

  Get a listing of all resource pools.
Note that there is always at least one resource pool: default.

  **Operation ID:** `ResourcePoolsHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of resource pools.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/resourcepools/: ResourcePoolsHandler create

  Creates a new resource pool.

  **Operation ID:** `ResourcePoolsHandler_create`

  **Request body (multipart/form-data):**

  - **`description`** (*string*, Optional): A brief description of the new resource pool.
  - **`name`** (*string*, Required): The new resource pool's name.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing details about your new resource pool.
  
  Content type: `application/json`

  **HTTP 400 BAD REQUEST**
  
  The resource pool already exists
  
  Content type: `text/plain`

````

## SSH Key

Operations for ssh key resources.

````{dropdown} DELETE /MAAS/api/2.0/account/prefs/sshkeys/{id}/: Delete an SSH key

  Deletes the SSH key with the given ID.

  **Operation ID:** `SSHKeyHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): An SSH key ID.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The requesting user does not own the key.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested SSH key is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/account/prefs/sshkeys/{id}/: Retrieve an SSH key

  Retrieves an SSH key with the given ID.

  **Operation ID:** `SSHKeyHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): An SSH key ID.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of imported keys.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested SSH key is not found.
  
  Content type: `text/plain`

````

## SSH Keys

Operations for ssh keys resources.

````{dropdown} GET /MAAS/api/2.0/account/prefs/sshkeys/: List SSH keys

  List all keys belonging to the requesting user.

  **Operation ID:** `SSHKeysHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of available SSH keys.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/account/prefs/sshkeys/: Add a new SSH key

  Add a new SSH key to the requesting or supplied user's account.

  **Operation ID:** `SSHKeysHandler_create`

  **Request body (multipart/form-data):**

  - **`key`** (*string*, Required): A public SSH key should be provided in the request payload as form data with the name 'key': `key: "key-type public-key-data"` - `key-type`: ecdsa-sha2-nistp256, ecdsa-sha2-nistp384, ecdsa-sha2-nistp521, ssh-ed25519, ssh-rsa - `public key data`: Base64-encoded key data.

  **Responses:**

  **HTTP 201 CREATED**
  
  A JSON object containing the new key.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/account/prefs/sshkeys/op-import: Import SSH keys

  Import the requesting user's SSH keys for a given protocol and authorization ID in protocol:auth_id format.

  **Operation ID:** `SSHKeysHandler_import`

  **Request body (multipart/form-data):**

  - **`keysource`** (*string*, Required): The source of the keys to import should be provided in the request payload as form data: E.g. `source:user` - `source`: lp (Launchpad), gh (GitHub) - `user`: User login

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of imported keys.
  
  Content type: `application/json`

````

## SSL Key

Operations for ssl key resources.

````{dropdown} DELETE /MAAS/api/2.0/account/prefs/sslkeys/{id}/: Delete an SSL key

  Deletes the SSL key with the given ID.

  **Operation ID:** `SSLKeyHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): An SSH key ID.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The requesting user does not own the key.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested SSH key is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/account/prefs/sslkeys/{id}/: Retrieve an SSL key

  Retrieves an SSL key with the given ID.

  **Operation ID:** `SSLKeyHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): An SSL key ID.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of imported keys.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The requesting user does not own the key.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested SSH key is not found.
  
  Content type: `text/plain`

````

## SSL Keys

Operations for ssl keys resources.

````{dropdown} GET /MAAS/api/2.0/account/prefs/sslkeys/: List keys

  List all keys belonging to the requesting user.

  **Operation ID:** `SSLKeysHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of SSL keys.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/account/prefs/sslkeys/: Add a new SSL key

  Add a new SSL key to the requesting user's account.

  **Operation ID:** `SSLKeysHandler_create`

  **Request body (multipart/form-data):**

  - **`key`** (*string*, Required): An SSL key should be provided in the request payload as form data with the name 'key': `key: "key data"` - `key data`: The contents of a pem file.

  **Responses:**

  **HTTP 201 CREATED**
  
  A JSON object containing the new key.
  
  Content type: `application/json`

````

## Space

Operations for space resources.

````{dropdown} DELETE /MAAS/api/2.0/spaces/{id}/: Delete a space

  Deletes a space with the given ID.

  **Operation ID:** `SpaceHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The space's ID.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested space is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/spaces/{id}/: Reads a space

  Gets a space with the given ID.

  **Operation ID:** `SpaceHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The space's ID.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the requested space.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested space is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/spaces/{id}/: Update space

  Updates a space with the given ID.

  **Operation ID:** `SpaceHandler_update`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The space's ID.

  **Request body (multipart/form-data):**

  - **`description`** (*string*, Optional): A description of the new space.
  - **`name`** (*string*, Required): The name of the new space.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the updated space.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested space is not found.
  
  Content type: `text/plain`

````

## Spaces

Operations for spaces resources.

````{dropdown} GET /MAAS/api/2.0/spaces/: List all spaces

  Generates a list of all spaces.

  **Operation ID:** `SpacesHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of space objects.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/spaces/: Create a space

  Create a new space.

  **Operation ID:** `SpacesHandler_create`

  **Request body (multipart/form-data):**

  - **`description`** (*string*, Optional): A description of the new space.
  - **`name`** (*string*, Required): The name of the new space.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the new space.
  
  Content type: `application/json`

  **HTTP 400 BAD REQUEST**
  
  Space with this name already exists.
  
  Content type: `text/plain`

````

## Static route

Operations for static route resources.

````{dropdown} DELETE /MAAS/api/2.0/static-routes/{id}/: Delete static route

  Deletes the static route with the given ID.

  **Operation ID:** `StaticRouteHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A static-route ID.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested static-route is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/static-routes/{id}/: Get a static route

  Gets a static route with the given ID.

  **Operation ID:** `StaticRouteHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A static-route ID.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the requested static route.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested static-route is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/static-routes/{id}/: Update a static route

  Updates a static route with the given ID.

  **Operation ID:** `StaticRouteHandler_update`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A static-route ID.

  **Request body (multipart/form-data):**

  - **`destination`** (*string*, Optional): Destination subnet name for the route.
  - **`gateway_ip`** (*string*, Optional): IP address of the gateway on the source subnet.
  - **`metric`** (*integer*, Optional): Weight of the route on a deployed machine.
  - **`source`** (*string*, Optional): Source subnet name for the route.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the updated static route object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested static-route is not found.
  
  Content type: `text/plain`

````

## Static routes

Operations for static routes resources.

````{dropdown} GET /MAAS/api/2.0/static-routes/: List static routes

  Lists all static routes.

  **Operation ID:** `StaticRoutesHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of static route objects.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/static-routes/: Create a static route

  Creates a static route.

  **Operation ID:** `StaticRoutesHandler_create`

  **Request body (multipart/form-data):**

  - **`destination`** (*string*, Required): Destination subnet name for the route.
  - **`gateway_ip`** (*string*, Required): IP address of the gateway on the source subnet.
  - **`metric`** (*integer*, Optional): Weight of the route on a deployed machine.
  - **`source`** (*string*, Required): Source subnet name for the route.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the new static route object.
  
  Content type: `application/json`

````

## Subnet

Operations for subnet resources.

````{dropdown} DELETE /MAAS/api/2.0/subnets/{id}/: Delete a subnet

  Delete a subnet with the given ID.

  **Operation ID:** `SubnetHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A subnet ID.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested subnet is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/subnets/{id}/: Get a subnet

  Get information about a subnet with the given ID.

  **Operation ID:** `SubnetHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A subnet ID.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the subnet.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested subnet is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/subnets/{id}/: Update a subnet

  Update a subnet with the given ID.

  **Operation ID:** `SubnetHandler_update`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A subnet ID.

  **Request body (multipart/form-data):**

  - **`allow_dns`** (*integer*, Optional): Configure MAAS DNS to allow DNS resolution from this subnet. '0' = False, '1' = True.
  - **`allow_proxy`** (*integer*, Optional): Configure maas-proxy to allow requests from this subnet. '0' = False, '1' = True.
  - **`cidr`** (*string*, Optional): The network CIDR for this subnet.
  - **`description`** (*string*, Optional): The subnet's description.
  - **`disabled_boot_architectures`** (*string*, Optional): A comma or space separated list of boot architectures which will not be responded to by isc-dhcpd. Values may be the MAAS name for the boot architecture, the IANA hex value, or the isc-dhcpd octet. Only managed subnets allow DHCP to be enabled on their related dynamic ranges. (Thus, dynamic ranges become "informational only"; an indication that another DHCP server is currently handling them, or that MAAS will handle them when the subnet is enabled for management.) Managed subnets do not allow IP allocation by default. The meaning of a "reserved" IP range is reversed for an unmanaged subnet. (That is, for managed subnets, "reserved" means "MAAS cannot allocate any IP address within this reserved block". For unmanaged subnets, "reserved" means "MAAS must allocate IP addresses only from reserved IP ranges."
  - **`dns_servers`** (*string*, Optional): Comma-separated list of DNS servers for this subnet.
  - **`fabric`** (*string*, Optional): Fabric for the subnet. Defaults to the fabric the provided VLAN belongs to, or defaults to the default fabric.
  - **`gateway_ip`** (*string*, Optional): The gateway IP address for this subnet.
  - **`managed`** (*integer*, Optional): In MAAS 2.0+, all subnets are assumed to be managed by default.
  - **`name`** (*string*, Optional): The subnet's name.
  - **`rdns_mode`** (*integer*, Optional): How reverse DNS is handled for this subnet. One of: - `0` Disabled: No reverse zone is created. - `1` Enabled: Generate reverse zone. - `2` RFC2317: Extends '1' to create the necessary parent zone with the appropriate CNAME resource records for the network, if the network is small enough to require the support described in RFC2317.
  - **`vid`** (*integer*, Optional): VID of the VLAN this subnet belongs to. Only used when vlan is not provided. Picks the VLAN with this VID in the provided fabric or the default fabric if one is not given.
  - **`vlan`** (*string*, Optional): VLAN this subnet belongs to. Defaults to the default VLAN for the provided fabric or defaults to the default VLAN in the default fabric (if unspecified).

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the updated subnet.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested subnet is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/subnets/{id}/op-ip_addresses: Summary of IP addresses

  Returns a summary of IP addresses assigned to this subnet.

  **Operation ID:** `SubnetHandler_ip_addresses`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A subnet ID.
  - **`with_username`** (*integer*, Optional): If '0', suppresses the display of usernames associated with each address. '1' = True, '0' = False. (Default: '1')
  - **`with_summary`** (*integer*, Optional): If '0', suppresses the display of nodes, BMCs, and and DNS records associated with each address. '1' = True, '0' = False. (Default: True)
  - **`with_node_summary`** (*integer*, Optional): Deprecated. Use 'with_summary'.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of IP addresses and information about each.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested subnet is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/subnets/{id}/op-reserved_ip_ranges: List reserved IP ranges

  Lists IP ranges currently reserved in the subnet.

  **Operation ID:** `SubnetHandler_reserved_ip_ranges`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A subnet ID.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of reserved IP ranges.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested subnet is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/subnets/{id}/op-statistics: Get subnet statistics

  Returns statistics for the specified subnet, including:
    - *num_available*: the number of available IP addresses - *largest_available*: the largest number of contiguous free IP   addresses - *num_unavailable*: the number of unavailable IP addresses - *total_addresses*: the sum of the available plus unavailable   addresses - *usage*: the (floating point) usage percentage of this subnet - *usage_string*: the (formatted unicode) usage percentage of this   subnet - *ranges*: the specific IP ranges present in ths subnet (if   specified) Note: to supply additional optional parameters for this request, add them to the request URI: e.g.
`/subnets/1/?op=statistics&include_suggestions=1`

  **Operation ID:** `SubnetHandler_statistics`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A subnet ID.
  - **`include_ranges`** (*integer*, Optional): If '1', includes detailed information about the usage of this range. '1' = True, '0' = False.
  - **`include_suggestions`** (*integer*, Optional): If '1', includes the suggested gateway and dynamic range for this subnet, if it were to be configured. '1' = True, '0' = False.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the statistics.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested subnet is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/subnets/{id}/op-unreserved_ip_ranges: List unreserved IP ranges

  Lists IP ranges currently unreserved in the subnet.

  **Operation ID:** `SubnetHandler_unreserved_ip_ranges`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): A subnet ID.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of unreserved IP ranges.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested subnet is not found.
  
  Content type: `text/plain`

````

## Subnets

Operations for subnets resources.

````{dropdown} GET /MAAS/api/2.0/subnets/: List all subnets

  Get a list of all subnets.

  **Operation ID:** `SubnetsHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing list of all known subnets.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/subnets/: Create a subnet

  Creates a new subnet.

  **Operation ID:** `SubnetsHandler_create`

  **Request body (multipart/form-data):**

  - **`active_discovery`** (*integer*, Optional): Configure MAAS to detect machines on the network by actively probing for devices.
  - **`allow_dns`** (*integer*, Optional): Configure MAAS DNS to allow DNS resolution from this subnet. '0' = False, '1' = True.
  - **`allow_proxy`** (*integer*, Optional): Configure maas-proxy to allow requests from this subnet. '0' = False, '1' = True.
  - **`cidr`** (*string*, Required): The network CIDR for this subnet.
  - **`description`** (*string*, Optional): The subnet's description.
  - **`disabled_boot_architectures`** (*string*, Optional): A comma or space separated list of boot architectures which will not be responded to by isc-dhcpd. Values may be the MAAS name for the boot architecture, the IANA hex value, or the isc-dhcpd octet. Only managed subnets allow DHCP to be enabled on their related dynamic ranges. (Thus, dynamic ranges become "informational only"; an indication that another DHCP server is currently handling them, or that MAAS will handle them when the subnet is enabled for management.) Managed subnets do not allow IP allocation by default. The meaning of a "reserved" IP range is reversed for an unmanaged subnet. (That is, for managed subnets, "reserved" means "MAAS cannot allocate any IP address within this reserved block". For unmanaged subnets, "reserved" means "MAAS must allocate IP addresses only from reserved IP ranges."
  - **`dns_servers`** (*string*, Optional): Comma-separated list of DNS servers for this subnet.
  - **`fabric`** (*string*, Optional): Fabric for the subnet. Defaults to the fabric the provided VLAN belongs to, or defaults to the default fabric.
  - **`gateway_ip`** (*string*, Optional): The gateway IP address for this subnet.
  - **`managed`** (*integer*, Optional): In MAAS 2.0+, all subnets are assumed to be managed by default.
  - **`name`** (*string*, Optional): The subnet's name.
  - **`rdns_mode`** (*integer*, Optional): How reverse DNS is handled for this subnet. One of: - `0` Disabled: No reverse zone is created. - `1` Enabled: Generate reverse zone. - `2` RFC2317: Extends '1' to create the necessary parent zone with the appropriate CNAME resource records for the network, if the network is small enough to require the support described in RFC2317.
  - **`vid`** (*integer*, Optional): VID of the VLAN this subnet belongs to. Only used when vlan is not provided. Picks the VLAN with this VID in the provided fabric or the default fabric if one is not given.
  - **`vlan`** (*string*, Optional): VLAN this subnet belongs to. Defaults to the default VLAN for the provided fabric or defaults to the default VLAN in the default fabric (if unspecified).

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the new subnet.
  
  Content type: `application/json`

````

## Tag

Operations for tag resources.

````{dropdown} DELETE /MAAS/api/2.0/tags/{name}/: Delete a tag

  Deletes a tag by name.

  **Operation ID:** `TagHandler_delete`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 
  - **`{name}`** (*object*, path parameter, Required): A tag name.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested tag name is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/tags/{name}/: Read a specific tag

  Returns a JSON object containing information about a specific tag.

  **Operation ID:** `TagHandler_read`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 
  - **`{name}`** (*object*, path parameter, Required): A tag name.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the requested tag.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested tag name is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/tags/{name}/: Update a tag

  Update elements of a given tag.

  **Operation ID:** `TagHandler_update`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 
  - **`{name}`** (*object*, path parameter, Required): The tag to update.

  **Request body (multipart/form-data):**

  - **`comment`** (*string*, Optional): A description of what the the tag will be used for in natural language.
  - **`definition`** (*string*, Optional): An XPATH query that is evaluated against the hardware_details stored for all nodes (i.e. the output of `lshw -xml`).
  - **`name`** (*string*, Optional): The new tag name. Because the name will be used in urls, it should be short.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON tag object.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested tag name is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/tags/{name}/op-devices: List devices by tag

  Get a JSON list containing device objects that match the given tag name.

  **Operation ID:** `TagHandler_devices`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 
  - **`{name}`** (*object*, path parameter, Required): A tag name.

  **Responses:**

  **HTTP 404 NOT FOUND**
  
  The requested tag name is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/tags/{name}/op-machines: List machines by tag

  Get a JSON list containing machine objects that match the given tag name.

  **Operation ID:** `TagHandler_machines`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 
  - **`{name}`** (*object*, path parameter, Required): A tag name.

  **Responses:**

  **HTTP 404 NOT FOUND**
  
  The requested tag name is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/tags/{name}/op-nodes: List nodes by tag

  Get a JSON list containing node objects that match the given tag name.

  **Operation ID:** `TagHandler_nodes`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 
  - **`{name}`** (*object*, path parameter, Required): A tag name.

  **Responses:**

  **HTTP 404 NOT FOUND**
  
  The requested tag name is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/tags/{name}/op-rack_controllers: List rack controllers by tag

  Get a JSON list containing rack-controller objects that match the given tag name.

  **Operation ID:** `TagHandler_rack_controllers`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 
  - **`{name}`** (*object*, path parameter, Required): A tag name.

  **Responses:**

  **HTTP 404 NOT FOUND**
  
  The requested tag name is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/tags/{name}/op-rebuild: Trigger a tag-node mapping rebuild

  Tells MAAS to rebuild the tag-to-node mappings.
This is a maintenance operation and should not be necessary under normal circumstances. Adding nodes or updating a tag definition should automatically trigger the mapping rebuild.

  **Operation ID:** `TagHandler_rebuild`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 
  - **`{name}`** (*object*, path parameter, Required): A tag name.

  **Responses:**

  **HTTP 404 NOT FOUND**
  
  The requested tag name is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/tags/{name}/op-region_controllers: List region controllers by tag

  Get a JSON list containing region-controller objects that match the given tag name.

  **Operation ID:** `TagHandler_region_controllers`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 
  - **`{name}`** (*object*, path parameter, Required): A tag name.

  **Responses:**

  **HTTP 404 NOT FOUND**
  
  The requested tag name is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/tags/{name}/op-update_nodes: Update nodes associated with this tag

  Add or remove nodes associated with the given tag.
Note that you must supply either the `add` or `remove` parameter.

  **Operation ID:** `TagHandler_update_nodes`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 
  - **`{name}`** (*object*, path parameter, Required): A tag name.

  **Request body (multipart/form-data):**

  - **`add`** (*string*, Optional): The system_id to tag.
  - **`definition`** (*string*, Optional): If given, the definition (XPATH expression) will be validated against the current definition of the tag. If the value does not match, MAAS assumes the worker is out of date and will drop the update.
  - **`rack_controller`** (*string*, Optional): The system ID of the rack controller that processed the given tag initially. If not given, the requester must be a MAAS admin. If given, the requester must be the rack controller.
  - **`remove`** (*string*, Optional): The system_id to untag.

  **Responses:**

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions required to update the nodes.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The requested tag name is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The supplied definition doesn't match the current definition.
  
  Content type: `text/plain`

````

## Tags

Operations for tags resources.

````{dropdown} GET /MAAS/api/2.0/tags/: List tags

  Outputs a JSON object containing an array of all currently defined tag objects.

  **Operation ID:** `TagsHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing an array of all currently defined tag objects.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/tags/: Create a new tag

  Create a new tag.

  **Operation ID:** `TagsHandler_create`

  **Request body (multipart/form-data):**

  - **`comment`** (*string*, Optional): A description of what the the tag will be used for in natural language.
  - **`definition`** (*string*, Optional): An XPATH query that is evaluated against the hardware_details stored for all nodes (i.e. the output of `lshw -xml`).
  - **`kernel_opts`** (*string*, Optional): Nodes associated with this tag will add this string to their kernel options when booting. The value overrides the global `kernel_opts` setting. If more than one tag is associated with a node, command line will be concatenated from all associated tags, in alphabetic tag name order.
  - **`name`** (*string*, Required): The new tag name. Because the name will be used in urls, it should be short.

  **Responses:**

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions required to create a tag.
  
  Content type: `text/plain`

````

## User

Operations for user resources.

````{dropdown} DELETE /MAAS/api/2.0/users/{username}/: Delete a user

  Deletes a given username.

  **Operation ID:** `UserHandler_delete`

  **Parameters:**

  - **`{username}`** (*string*, path parameter, Required): 
  - **`{username}`** (*string*, path parameter, Required): The username to delete.
  - **`transfer_resources_to`** (*string*, Optional): An optional username. If supplied, the allocated resources of the user being deleted will be transferred to this user. A user can't be removed unless its resources (machines, IP addresses, .), are released or transfered to another user.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

````

````{dropdown} GET /MAAS/api/2.0/users/{username}/: Retrieve user details

  Retrieve a user's details.

  **Operation ID:** `UserHandler_read`

  **Parameters:**

  - **`{username}`** (*string*, path parameter, Required): 
  - **`{username}`** (*string*, path parameter, Required): A username.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing user information.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The given user was not found.
  
  Content type: `text/plain`

````

## UserGroup

Operations for usergroup resources.

````{dropdown} DELETE /MAAS/api/2.0/groups/{id}/: UserGroupHandler delete

  Deletes a user group.

  **Operation ID:** `UserGroupHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*object*, path parameter, Required): A group ID.

  **Responses:**

  **HTTP 200 OK**
  
  204

````

````{dropdown} GET /MAAS/api/2.0/groups/{id}/: UserGroupHandler read

  Returns a user group.

  **Operation ID:** `UserGroupHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*object*, path parameter, Required): A group ID.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing group information.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The group is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/groups/{id}/: UserGroupHandler update

  Updates a user group.

  **Operation ID:** `UserGroupHandler_update`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*object*, path parameter, Required): A group ID.

  **Request body (multipart/form-data):**

  - **`description`** (*string*, Optional): The group description.
  - **`name`** (*string*, Optional): The group name.

  **Responses:**

  **HTTP 200 OK**
  
  200

  **HTTP 404 NOT FOUND**
  
  The group is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/groups/{id}/op-add_entitlement: UserGroupHandler add_entitlement

  Adds an entitlement to a user group.

  **Operation ID:** `UserGroupHandler_add_entitlement`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*object*, path parameter, Required): A group ID.

  **Request body (multipart/form-data):**

  - **`entitlement`** (*string*, Required): The entitlement name.
  - **`resource_id`** (*integer*, Required): The resource ID. Must be 0 for 'maas' type.
  - **`resource_type`** (*string*, Required): The resource type ('maas' or 'pool').

  **Responses:**

  **HTTP 200 OK**
  
  200

  **HTTP 400 BAD REQUEST**
  
  Invalid request parameters.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The group or resource is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/groups/{id}/op-add_member: UserGroupHandler add_member

  Adds a user to a user group.

  **Operation ID:** `UserGroupHandler_add_member`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*object*, path parameter, Required): A group ID.

  **Request body (multipart/form-data):**

  - **`username`** (*string*, Required): The username to add.

  **Responses:**

  **HTTP 200 OK**
  
  200

  **HTTP 400 BAD REQUEST**
  
  username is required.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The group or user is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The user is already a member of the group.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/groups/{id}/op-list_entitlements: UserGroupHandler list_entitlements

  Lists entitlements of a user group.

  **Operation ID:** `UserGroupHandler_list_entitlements`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*object*, path parameter, Required): A group ID.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON list of entitlements.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The group is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/groups/{id}/op-list_members: UserGroupHandler list_members

  Lists members of a user group.

  **Operation ID:** `UserGroupHandler_list_members`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*object*, path parameter, Required): A group ID.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON list of group members.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The group is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/groups/{id}/op-remove_entitlement: UserGroupHandler remove_entitlement

  Removes an entitlement from a user group.

  **Operation ID:** `UserGroupHandler_remove_entitlement`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*object*, path parameter, Required): A group ID.

  **Request body (multipart/form-data):**

  - **`entitlement`** (*string*, Required): The entitlement name.
  - **`resource_id`** (*integer*, Required): The resource ID.
  - **`resource_type`** (*string*, Required): The resource type ('maas' or 'pool').

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 400 BAD REQUEST**
  
  Invalid request parameters.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The group is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/groups/{id}/op-remove_member: UserGroupHandler remove_member

  Removes a user from a user group.

  **Operation ID:** `UserGroupHandler_remove_member`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*object*, path parameter, Required): A group ID.

  **Request body (multipart/form-data):**

  - **`username`** (*string*, Required): The username to remove.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 400 BAD REQUEST**
  
  username is required.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  The user is not found.
  
  Content type: `text/plain`

````

## UserGroups

Operations for usergroups resources.

````{dropdown} GET /MAAS/api/2.0/groups/: UserGroupsHandler read

  Lists all user groups.

  **Operation ID:** `UserGroupsHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  200

````

````{dropdown} POST /MAAS/api/2.0/groups/: UserGroupsHandler create

  Creates a new user group.

  **Operation ID:** `UserGroupsHandler_create`

  **Request body (multipart/form-data):**

  - **`description`** (*string*, Optional): The group description.
  - **`name`** (*string*, Required): The group name.

  **Responses:**

  **HTTP 200 OK**
  
  200

  **HTTP 400 BAD REQUEST**
  
  Name is required.
  
  Content type: `text/plain`

````

## Users

Operations for users resources.

````{dropdown} GET /MAAS/api/2.0/users/: List users

  List users

  **Operation ID:** `UsersHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of users.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/users/: Create a MAAS user account

  Creates a MAAS user account.
This is not safe: the password is sent in plaintext.  Avoid it for production, unless you are confident that you can prevent eavesdroppers from observing the request.

  **Operation ID:** `UsersHandler_create`

  **Request body (multipart/form-data):**

  - **`email`** (*string*, Required): Email address for the new user.
  - **`is_superuser`** (*boolean*, Required): Whether the new user is to be an administrator. ('0' = False, '1' = True)
  - **`password`** (*string*, Required): Password for the new user.
  - **`username`** (*string*, Required): Identifier-style username for the new user.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the new user.
  
  Content type: `application/json`

  **HTTP 400 BAD REQUEST**
  
  Mandatory parameters are missing.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/users/op-whoami: Retrieve logged-in user

  Returns the currently logged-in user.

  **Operation ID:** `UsersHandler_whoami`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the currently logged-in user.
  
  Content type: `application/json`

````

## VLAN

Operations for vlan resources.

````{dropdown} DELETE /MAAS/api/2.0/fabrics/{fabric_id}/vlans/{vid}/: Delete a VLAN

  Delete VLAN on a given fabric.

  **Operation ID:** `VlanHandler_delete`

  **Parameters:**

  - **`{fabric_id}`** (*string*, path parameter, Required): 
  - **`{vid}`** (*string*, path parameter, Required): 
  - **`{fabric_id}`** (*integer*, path parameter, Required): Fabric ID containing the VLAN to delete.
  - **`{vid}`** (*integer*, path parameter, Required): VLAN ID of the VLAN to delete.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested fabric_id or vid is not found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/fabrics/{fabric_id}/vlans/{vid}/: Retrieve VLAN

  Retrieves a VLAN on a given fabric_id.

  **Operation ID:** `VlanHandler_read`

  **Parameters:**

  - **`{fabric_id}`** (*string*, path parameter, Required): 
  - **`{vid}`** (*string*, path parameter, Required): 
  - **`{fabric_id}`** (*integer*, path parameter, Required): The fabric_id containing the VLAN.
  - **`{vid}`** (*integer*, path parameter, Required): The VLAN ID.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the requested VLAN.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested fabric_id or vid is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/fabrics/{fabric_id}/vlans/{vid}/: Update VLAN

  Updates a given VLAN.

  **Operation ID:** `VlanHandler_update`

  **Parameters:**

  - **`{fabric_id}`** (*string*, path parameter, Required): 
  - **`{vid}`** (*string*, path parameter, Required): 
  - **`{fabric_id}`** (*integer*, path parameter, Required): Fabric ID containing the VLAN.
  - **`{vid}`** (*integer*, path parameter, Required): VLAN ID of the VLAN.

  **Request body (multipart/form-data):**

  - **`description`** (*string*, Optional): Description of the VLAN.
  - **`dhcp_on`** (*boolean*, Optional): Whether or not DHCP should be managed on the VLAN.
  - **`mtu`** (*integer*, Optional): The MTU to use on the VLAN.
  - **`name`** (*string*, Optional): Name of the VLAN.
  - **`primary_rack`** (*string*, Optional): The primary rack controller managing the VLAN (system_id).
  - **`relay_vlan`** (*integer*, Optional): Relay VLAN ID. Only set when this VLAN will be using a DHCP relay to forward DHCP requests to another VLAN that MAAS is managing. MAAS will not run the DHCP relay itself, it must be configured to proxy reqests to the primary and/or secondary rack controller interfaces for the VLAN specified in this field.
  - **`secondary_rack`** (*string*, Optional): The secondary rack controller managing the VLAN (system_id).
  - **`space`** (*string*, Optional): The space this VLAN should be placed in. Passing in an empty string (or the string 'undefined') will cause the VLAN to be placed in the 'undefined' space.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the updated VLAN.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested fabric_id or vid is not found.
  
  Content type: `text/plain`

````

## VLANs

Operations for vlans resources.

````{dropdown} GET /MAAS/api/2.0/fabrics/{fabric_id}/vlans/: List VLANs

  List all VLANs belonging to given fabric.

  **Operation ID:** `VlansHandler_read`

  **Parameters:**

  - **`{fabric_id}`** (*string*, path parameter, Required): 
  - **`{fabric_id}`** (*integer*, path parameter, Required): The fabric for which to list the VLANs.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of VLANs in the given fabric.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested fabric_id is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/fabrics/{fabric_id}/vlans/: Create a VLAN

  Creates a new VLAN.

  **Operation ID:** `VlansHandler_create`

  **Parameters:**

  - **`{fabric_id}`** (*string*, path parameter, Required): 
  - **`{fabric_id}`** (*integer*, path parameter, Required): The fabric_id on which to add the new VLAN.

  **Request body (multipart/form-data):**

  - **`description`** (*string*, Optional): Description of the new VLAN.
  - **`mtu`** (*integer*, Optional): The MTU to use on the VLAN.
  - **`name`** (*string*, Optional): Name of the VLAN.
  - **`space`** (*string*, Optional): The space this VLAN should be placed in. Passing in an empty string (or the string 'undefined') will cause the VLAN to be placed in the 'undefined' space.
  - **`vid`** (*integer*, Required): VLAN ID of the new VLAN.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing information about the new VLAN.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested fabric_id is not found.
  
  Content type: `text/plain`

````

## VMFS datastore

Operations for vmfs datastore resources.

````{dropdown} DELETE /MAAS/api/2.0/nodes/{system_id}/vmfs-datastore/{id}/: Delete the specified VMFS datastore.

  Delete a VMFS datastore with the given id from the machine with the given system_id.

  **Operation ID:** `VmfsDatastoreHandler_delete`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id containing the VMFS datastore.
  - **`{id}`** (*integer*, path parameter, Required): The id of the VMFS datastore.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/vmfs-datastore/{id}/: Read a VMFS datastore.

  Read a VMFS datastore with the given id on the machine with the given system_id.

  **Operation ID:** `VmfsDatastoreHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id on which to create the VMFS datastore.
  - **`{id}`** (*integer*, path parameter, Required): The id of the VMFS datastore.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested VMFS data.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/nodes/{system_id}/vmfs-datastore/{id}/: Update a VMFS datastore.

  Update a VMFS datastore with the given id on the machine with the given system_id.

  **Operation ID:** `VmfsDatastoreHandler_update`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id containing the VMFS datastore.
  - **`{id}`** (*integer*, path parameter, Required): The id of the VMFS datastore.

  **Request body (multipart/form-data):**

  - **`add_block_devices`** (*string*, Optional): Block devices to add to the VMFS datastore.
  - **`add_partitions`** (*string*, Optional): Partitions to add to the VMFS datastore.
  - **`name`** (*string*, Optional): Name of the VMFS datastore.
  - **`remove_partitions`** (*string*, Optional): Partitions to remove from the VMFS datastore.
  - **`uuid`** (*string*, Optional): UUID of the VMFS datastore.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested VMFS datastore.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

## VMFS datastores

Operations for vmfs datastores resources.

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/vmfs-datastores/: List all VMFS datastores.

  List all VMFS datastores belonging to a machine with the given system_id.

  **Operation ID:** `VmfsDatastoresHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id containing the VMFS datastores.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of VMFS datastore objects.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/vmfs-datastores/: Create a VMFS datastore.

  Create a VMFS datastore belonging to a machine with the given system_id.
Note that at least one valid block device or partition is required.

  **Operation ID:** `VmfsDatastoresHandler_create`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id on which to create the VMFS datastore.

  **Request body (multipart/form-data):**

  - **`block_devices`** (*string*, Optional): Block devices to add to the VMFS datastore.
  - **`name`** (*string*, Required): Name of the VMFS datastore.
  - **`partitions`** (*string*, Optional): Partitions to add to the VMFS datastore.
  - **`uuid`** (*string*, Optional): (optional) UUID of the VMFS group.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new VMFS datastore.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

## Virtual Machine Cluster

Operations for virtual machine cluster resources.

````{dropdown} DELETE /MAAS/api/2.0/vm-clusters/{id}: Deletes a VM cluster

  Deletes a VM cluster with the given ID.

  **Operation ID:** `VmClusterHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The VM cluster's ID.
  - **`decompose`** (*boolean*, Optional): Whether to also also decompose all machines in the VM cluster on removal. If not provided, machines will not be removed.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions to delete the VM cluster.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  No VM cluster with that ID can be found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/vm-clusters/{id}: VmClusterHandler read

  Read operations for the VM Cluster object A VM Cluster is identified by its id

  **Operation ID:** `VmClusterHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 

  **Responses:**

  **HTTP 404 NOT FOUND**
  
  'str' object has no attribute 'has_model'
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/vm-clusters/{id}: Update VMCluster

  Update a specific VMCluster by ID.

  **Operation ID:** `VmClusterHandler_update`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*object*, path parameter, Required): The VMCluster's ID.

  **Request body (multipart/form-data):**

  - **`name`** (*string*, Optional): The VMCluster's name.
  - **`pool`** (*string*, Optional): The name of the resource pool associated with this VM Cluster - this change is propagated to VMHosts
  - **`zone`** (*string*, Optional): The VMCluster's zone.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON VMClister object.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  403 - The current user does not have permission to update the VMCluster.

  **HTTP 404 NOT FOUND**
  
  404 - The VMCluster's ID was not found.

````

## Virtual Machine Clusters

Operations for virtual machine clusters resources.

````{dropdown} GET /MAAS/api/2.0/vm-clusters/: List VM Clusters

  Get a listing of all VM Clusters

  **Operation ID:** `VmClustersHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of VM Cluster objects.
  
  Content type: `application/json`

````

## Volume group

Operations for volume group resources.

````{dropdown} DELETE /MAAS/api/2.0/nodes/{system_id}/volume-group/{id}/: Delete volume group

  Delete a volume group with the given id from the machine with the given system_id.

  **Operation ID:** `VolumeGroupHandler_delete`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id containing the volume group.
  - **`{id}`** (*integer*, path parameter, Required): The id of the volume group.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/volume-group/{id}/: Read a volume group

  Read a volume group with the given id on the machine with the given system_id.

  **Operation ID:** `VolumeGroupHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id on which to create the volume group.
  - **`{id}`** (*integer*, path parameter, Required): The id of the volume group.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested volume group.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/nodes/{system_id}/volume-group/{id}/: Update a volume group

  Update a volume group with the given id on the machine with the given system_id.

  **Operation ID:** `VolumeGroupHandler_update`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id containing the volume group.
  - **`{id}`** (*integer*, path parameter, Required): The id of the volume group.

  **Request body (multipart/form-data):**

  - **`add_block_devices`** (*string*, Optional): Block devices to add to the volume group.
  - **`add_partitions`** (*string*, Optional): Partitions to add to the volume group.
  - **`name`** (*string*, Optional): Name of the volume group.
  - **`remove_block_devices`** (*string*, Optional): Block devices to remove from the volume group.
  - **`remove_partitions`** (*string*, Optional): Partitions to remove from the volume group.
  - **`uuid`** (*string*, Optional): UUID of the volume group.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested volume group.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/volume-group/{id}/op-create_logical_volume: Create a logical volume

  Create a logical volume in the volume group with the given id on the machine with the given system_id.

  **Operation ID:** `VolumeGroupHandler_create_logical_volume`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id containing the volume group.
  - **`{id}`** (*integer*, path parameter, Required): The id of the volume group.

  **Request body (multipart/form-data):**

  - **`name`** (*string*, Required): Name of the logical volume.
  - **`size`** (*string*, Optional): (optional) Size of the logical volume. Must be larger than or equal to 4,194,304 bytes. E.g. `4194304`. Will default to free space in the volume group if not given.
  - **`uuid`** (*string*, Optional): (optional) UUID of the logical volume.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the requested volume group.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/volume-group/{id}/op-delete_logical_volume: Delete a logical volume

  Delete a logical volume in the volume group with the given id on the machine with the given system_id.
Note: this operation returns HTTP status code 204 even if the logical volume id does not exist.

  **Operation ID:** `VolumeGroupHandler_delete_logical_volume`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id containing the volume group.
  - **`{id}`** (*integer*, path parameter, Required): The id of the volume group.

  **Request body (multipart/form-data):**

  - **`id`** (*integer*, Required): The logical volume id.

  **Responses:**

  **HTTP 200 OK**
  
  204

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

## Volume groups

Operations for volume groups resources.

````{dropdown} GET /MAAS/api/2.0/nodes/{system_id}/volume-groups/: List all volume groups

  List all volume groups belonging to a machine with the given system_id.

  **Operation ID:** `VolumeGroupsHandler_read`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id containing the volume groups.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of volume-group objects.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/nodes/{system_id}/volume-groups/: Create a volume group

  Create a volume group belonging to a machine with the given system_id.
Note that at least one valid block device or partition is required.

  **Operation ID:** `VolumeGroupsHandler_create`

  **Parameters:**

  - **`{system_id}`** (*string*, path parameter, Required): 
  - **`{system_id}`** (*string*, path parameter, Required): The machine system_id on which to create the volume group.

  **Request body (multipart/form-data):**

  - **`block_devices`** (*string*, Optional): Block devices to add to the volume group.
  - **`name`** (*string*, Required): Name of the volume group.
  - **`partitions`** (*string*, Optional): Partitions to add to the volume group.
  - **`uuid`** (*string*, Optional): (optional) UUID of the volume group.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new volume group.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The requested machine is not found.
  
  Content type: `text/plain`

  **HTTP 409 CONFLICT**
  
  The requested machine is not ready.
  
  Content type: `text/plain`

````

## Zone

Operations for zone resources.

````{dropdown} DELETE /MAAS/api/2.0/zones/{name}/: ZoneHandler delete

  Deletes a zone.

  **Operation ID:** `ZoneHandler_delete`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 
  - **`{name}`** (*object*, path parameter, Required): The zone to delete.

  **Responses:**

  **HTTP 200 OK**
  
  An empty string
  
  Content type: `text/plain`

  **HTTP 204 NO CONTENT**
  
  An empty string
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/zones/{name}/: ZoneHandler read

  Returns a named zone.

  **Operation ID:** `ZoneHandler_read`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 
  - **`{name}`** (*object*, path parameter, Required): A zone name

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing zone information
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  The zone name is not found.
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/zones/{name}/: ZoneHandler update

  Updates a zone's name or description.
Note that only 'name' and 'description' parameters are honored. Others, such as 'resource-uri' or 'id' will be ignored.

  **Operation ID:** `ZoneHandler_update`

  **Parameters:**

  - **`{name}`** (*string*, path parameter, Required): 
  - **`{name}`** (*object*, path parameter, Required): The zone to update.

  **Request body (multipart/form-data):**

  - **`description`** (*string*, Optional): A brief description of the new zone.
  - **`name`** (*string*, Optional): The zone's new name.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing details about your new zone.
  
  Content type: `application/json`

  **HTTP 404 NOT FOUND**
  
  Zone not found
  
  Content type: `text/plain`

````

## Zones

Operations for zones resources.

````{dropdown} GET /MAAS/api/2.0/zones/: ZonesHandler read

  Get a listing of all zones. Note that there is always at least one zone: default.

  **Operation ID:** `ZonesHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of zones.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/zones/: ZonesHandler create

  Creates a new zone.

  **Operation ID:** `ZonesHandler_create`

  **Request body (multipart/form-data):**

  - **`description`** (*string*, Optional): A brief description of the new zone.
  - **`name`** (*string*, Required): The new zone's name.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing details about your new zone.
  
  Content type: `application/json`

  **HTTP 400 BAD REQUEST**
  
  The zone already exists
  
  Content type: `text/plain`

````

## vm host

Operations for vm host resources.

````{dropdown} DELETE /MAAS/api/2.0/vm-hosts/{id}/: Deletes a VM host

  Deletes a VM host with the given ID.

  **Operation ID:** `VmHostHandler_delete`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The VM host's ID.
  - **`decompose`** (*boolean*, Optional): Whether to also also decompose all machines in the VM host on removal. If not provided, machines will not be removed.

  **Responses:**

  **HTTP 204 NO CONTENT**
  
  204

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions to delete the VM host.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  No VM host with that ID can be found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/vm-hosts/{id}/: VmHostHandler read

  Manage an individual VM host.
A VM host is identified by its id.

  **Operation ID:** `VmHostHandler_read`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 

  **Responses:**

  **HTTP 404 NOT FOUND**
  
  'str' object has no attribute 'has_model'
  
  Content type: `text/plain`

````

````{dropdown} PUT /MAAS/api/2.0/vm-hosts/{id}/: Update a specific VM host

  Update a specific VM host by ID.
Note: A VM host's 'type' cannot be updated. The VM host must be deleted and re-added to change the type.

  **Operation ID:** `VmHostHandler_update`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*object*, path parameter, Required): The VM host's ID.

  **Request body (multipart/form-data):**

  - **`cpu_over_commit_ratio`** (*integer*, Optional): CPU overcommit ratio (0-10)
  - **`default_macvlan_mode`** (*string*, Optional): Default macvlan mode for VM hosts that use it: bridge, passthru, private, vepa.
  - **`default_storage_pool`** (*string*, Optional): Default KVM storage pool to use when the VM host has storage pools.
  - **`memory_over_commit_ratio`** (*integer*, Optional): CPU overcommit ratio (0-10)
  - **`name`** (*string*, Optional): The VM host's name.
  - **`pool`** (*string*, Optional): The name of the resource pool associated with this VM host - composed machines will be assigned to this resource pool by default.
  - **`power_address`** (*string*, Optional): Address for power control of the VM host.
  - **`power_pass`** (*string*, Optional): Password for access to power control of the VM host.
  - **`tags`** (*string*, Optional): Tag or tags (command separated) associated with the VM host.
  - **`zone`** (*string*, Optional): The VM host's zone.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON VM host object.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  403 - The current user does not have permission to update the VM host.

  **HTTP 404 NOT FOUND**
  
  404 - The VM host's ID was not found.

````

````{dropdown} POST /MAAS/api/2.0/vm-hosts/{id}/op-add_tag: Add a tag to a VM host

  Adds a tag to a given VM host.

  **Operation ID:** `VmHostHandler_add_tag`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The VM host's ID.

  **Request body (multipart/form-data):**

  - **`tag`** (*string*, Required): The tag to add.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions to delete the VM host.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  No VM host with that ID can be found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/vm-hosts/{id}/op-compose: Compose a virtual machine on the host.

  Compose a new machine from a VM host.

  **Operation ID:** `VmHostHandler_compose`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 

  **Request body (multipart/form-data):**

  - **`architecture`** (*string*, Optional): The architecture of the new machine (e.g. amd64). This must be an architecture the VM host supports.
  - **`cores`** (*integer*, Optional): The minimum number of CPU cores.
  - **`cpu_speed`** (*integer*, Optional): The minimum CPU speed, specified in MHz.
  - **`domain`** (*integer*, Optional): The ID of the domain in which to put the newly composed machine.
  - **`hostname`** (*string*, Optional): The hostname of the newly composed machine.
  - **`hugepages_backed`** (*boolean*, Optional): Whether to request hugepages backing for the machine.
  - **`interfaces`** (*string*, Optional): A labeled constraint map associating constraint labels with desired interface properties. MAAS will assign interfaces that match the given interface properties. Format: `label:key=value,key=value,.` Keys: - `id`: Matches an interface with the specific id - `fabric`: Matches an interface attached to the specified fabric. - `fabric_class`: Matches an interface attached to a fabric with the specified class. - `ip`: Matches an interface whose VLAN is on the subnet implied by the given IP address, and allocates the specified IP address for the machine on that interface (if it is available). - `mode`: Matches an interface with the specified mode. (Currently, the only supported mode is "unconfigured".) - `name`: Matches an interface with the specified name. (For example, "eth0".) - `hostname`: Matches an interface attached to the node with the specified hostname. - `subnet`: Matches an interface attached to the specified subnet. - `space`: Matches an interface attached to the specified space. - `subnet_cidr`: Matches an interface attached to the specified subnet CIDR. (For example, "192.168.0.0/24".) - `type`: Matches an interface of the specified type. (Valid types: "physical", "vlan", "bond", "bridge", or "unknown".) - `vlan`: Matches an interface on the specified VLAN. - `vid`: Matches an interface on a VLAN with the specified VID. - `tag`: Matches an interface tagged with the specified tag.
  - **`memory`** (*integer*, Optional): The minimum amount of memory, specified in MiB (e.g. 2 MiB = 2*1024*1024).
  - **`pinned_cores`** (*integer*, Optional): List of host CPU cores to pin the VM to. If this is passed, the "cores" parameter is ignored.
  - **`pool`** (*integer*, Optional): The ID of the pool in which to put the newly composed machine.
  - **`storage`** (*string*, Optional): A list of storage constraint identifiers in the form `label:size(tag,tag,.), label:size(tag,tag,.)`. For more information please see the CLI VM host management page of the official MAAS documentation.
  - **`zone`** (*integer*, Optional): The ID of the zone in which to put the newly composed machine.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the new machine ID and resource URI.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions to delete the VM host.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  No VM host with that ID can be found.
  
  Content type: `text/plain`

````

````{dropdown} GET /MAAS/api/2.0/vm-hosts/{id}/op-parameters: Obtain VM host parameters

  This returns a VM host's configuration parameters. For some types of VM host, this will include private information such as passwords and secret keys.
Note: This method is reserved for admin users.

  **Operation ID:** `VmHostHandler_parameters`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The VM host's ID.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing the VM host's configuration parameters.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions to delete the VM host.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  No VM host with that ID can be found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/vm-hosts/{id}/op-refresh: Refresh a VM host

  Performs VM host discovery and updates all discovered information and discovered machines.

  **Operation ID:** `VmHostHandler_refresh`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The VM host's ID.

  **Responses:**

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions to delete the VM host.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  No VM host with that ID can be found.
  
  Content type: `text/plain`

````

````{dropdown} POST /MAAS/api/2.0/vm-hosts/{id}/op-remove_tag: Remove a tag from a VM host

  Removes a given tag from a VM host.

  **Operation ID:** `VmHostHandler_remove_tag`

  **Parameters:**

  - **`{id}`** (*string*, path parameter, Required): 
  - **`{id}`** (*integer*, path parameter, Required): The VM host's ID.

  **Request body (multipart/form-data):**

  - **`tag`** (*string*, Required): The tag to add.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions to delete the VM host.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  No VM host with that ID can be found.
  
  Content type: `text/plain`

````

## vm hosts

Operations for vm hosts resources.

````{dropdown} GET /MAAS/api/2.0/vm-hosts/: List VM hosts

  Get a listing of all VM hosts.

  **Operation ID:** `VmHostsHandler_read`

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a list of VM host objects.
  
  Content type: `application/json`

````

````{dropdown} POST /MAAS/api/2.0/vm-hosts/: Create a VM host

  Create or discover a new VM host.

  **Operation ID:** `VmHostsHandler_create`

  **Request body (multipart/form-data):**

  - **`certificate`** (*string*, Optional): X.509 certificate used to verify the identity of the user. If `certificate` and `key` are not provided, and the VM created is LXD type, a X.509 certificate will be created.
  - **`key`** (*string*, Optional): private key used for authentication. If `certificate` and `key` are not provided, and the VM created is LXD type, a RSA key will be created.
  - **`name`** (*string*, Optional): The new VM host's name.
  - **`pool`** (*string*, Optional): The name of the resource pool the new VM host will belong to. Machines composed from this VM host will be assigned to this resource pool by default.
  - **`power_address`** (*string*, Required): Address that gives MAAS access to the VM host power control. For example, for virsh `qemu+ssh:/172.16.99.2/system` For `lxd`, this is just the address of the host.
  - **`power_pass`** (*string*, Required): Password to use for power control of the VM host. Required `virsh` VM hosts that do not have SSH set up for public-key authentication and for `lxd` if the MAAS certificate is not registered already in the LXD server.
  - **`power_user`** (*string*, Required): Username to use for power control of the VM host. Required for `virsh` VM hosts that do not have SSH set up for public-key authentication.
  - **`project`** (*string*, Optional): For `lxd` VM hosts, the project that MAAS will manage. If not provided, the `default` project will be used. If a nonexistent name is given, a new project with that name will be created.
  - **`tags`** (*string*, Optional): A tag or list of tags ( comma delimited) to assign to the new VM host.
  - **`type`** (*string*, Required): The type of VM host to create: `lxd` or `virsh`.
  - **`zone`** (*string*, Optional): The new VM host's zone.

  **Responses:**

  **HTTP 200 OK**
  
  A JSON object containing a VM host object.
  
  Content type: `application/json`

  **HTTP 403 FORBIDDEN**
  
  The user does not have the permissions to delete the VM host.
  
  Content type: `text/plain`

  **HTTP 404 NOT FOUND**
  
  No VM host with that ID can be found.
  
  Content type: `text/plain`

  **HTTP 503 SERVICE UNAVAILABLE**
  
  MAAS could not find or could not authenticate with the VM host.
  
  Content type: `text/plain`

````
