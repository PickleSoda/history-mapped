<?php

declare(strict_types=1);

namespace App\Http\Api\V1\Controllers;

use App\Http\Api\V1\Resources\MeResource;
use App\Http\Controllers\Controller;
use Illuminate\Http\Request;

class MeController extends Controller
{
    /**
     * GET /api/v1/me
     *
     * The signed-in account with its roles and capability flags.
     */
    public function show(Request $request): MeResource
    {
        return new MeResource($request->user());
    }
}
