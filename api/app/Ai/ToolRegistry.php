<?php

namespace App\Ai;

use App\Ai\Tools\AgentTool;

class ToolRegistry
{
    /** @var array<string,string> name => container binding/class */
    private array $map = [];

    public function register(string $name, string $binding): void
    {
        $this->map[$name] = $binding;
    }

    public function resolve(string $name): AgentTool
    {
        abort_unless(isset($this->map[$name]), 422, "Unknown tool: {$name}");

        return app($this->map[$name]);
    }
}
