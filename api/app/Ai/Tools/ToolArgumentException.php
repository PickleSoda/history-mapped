<?php

namespace App\Ai\Tools;

use InvalidArgumentException;

/**
 * A tool argument the model can fix. Its message is returned to the model as
 * the tool result (other failures get a generic error), so phrase it as what
 * to send instead.
 */
class ToolArgumentException extends InvalidArgumentException {}
